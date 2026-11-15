from __future__ import annotations
import io, re, json
# Render redeploy marker: keep the production service aligned with main.
from html import unescape
from urllib.request import Request as UrlRequest, urlopen
from pathlib import Path
from typing import Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:
    YouTubeTranscriptApi = None
try:
    import yt_dlp
except Exception:
    yt_dlp = None

app = FastAPI(title='YouTube Transcript Studio', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

class ExtractRequest(BaseModel):
    url: str
    language: str = 'auto'
    include_timestamps: bool = False
    clean: bool = False
    remove_fillers: bool = False
    add_paragraphs: bool = True
    preserve_original: bool = True

def video_id(url: str) -> str:
    patterns = [r'youtube\.com/watch\?[^#]*v=([\w-]{11})', r'youtu\.be/([\w-]{11})', r'youtube\.com/(?:shorts|live)/([\w-]{11})']
    for pattern in patterns:
        match = re.search(pattern, url, re.I)
        if match: return match.group(1)
    raise HTTPException(422, 'Enter a valid YouTube watch, short, live, or youtu.be URL.')

def clean_text(text: str, lang: str, remove_fillers: bool) -> str:
    text = re.sub(r'\s+', ' ', text).strip()
    if remove_fillers and not lang.startswith(('zh', 'ja', 'ko')):
        text = re.sub(r'\b(?:um+|uh+|er+|like)(?=\s|[,.;!?]|$)', '', text, flags=re.I)
        text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def timestamp(sec: float) -> str:
    total = int(sec); h, rem = divmod(total, 3600); m, s = divmod(rem, 60)
    return f'{h:02d}:{m:02d}:{s:02d}'

def direct_caption_fallback(vid: str, language: str):
    request = UrlRequest(f'https://www.youtube.com/watch?v={vid}', headers={'User-Agent': 'Mozilla/5.0'})
    page = urlopen(request, timeout=12).read().decode('utf-8', 'ignore')
    match = re.search(r'"captionTracks":(\[.*?\])', page)
    if not match: raise RuntimeError('No captionTracks in player response')
    tracks = json.loads(match.group(1).replace('\\u0026', '&'))
    if language == 'auto':
        track = next((t for t in tracks if t.get('languageCode') in ('en', 'zh-Hans', 'zh-Hant')), tracks[0])
    else:
        track = next((t for t in tracks if t.get('languageCode') == language), None)
        if track is None: raise RuntimeError('Requested language track is unavailable')
    xml = urlopen(UrlRequest(track['baseUrl'], headers={'User-Agent': 'Mozilla/5.0'}), timeout=12).read().decode('utf-8', 'ignore')
    items = []
    for start, duration, text in re.findall(r'<text start="([^"]+)"(?: dur="([^"]+)")?>(.*?)</text>', xml, re.S):
        text = re.sub(r'<[^>]+>', '', unescape(text)).replace('&#39;', "'").strip()
        if text: items.append({'text': text, 'start': float(start), 'duration': float(duration or 0)})
    if not items: raise RuntimeError('Caption XML was empty')
    return items, track.get('languageCode', language), [t.get('languageCode') for t in tracks]

def ytdlp_caption_fallback(vid: str, language: str):
    if not yt_dlp: raise RuntimeError('yt-dlp is unavailable')
    with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'skip_download': True, 'noplaylist': True}) as ydl:
        info = ydl.extract_info(f'https://www.youtube.com/watch?v={vid}', download=False)
    tracks = info.get('subtitles') or info.get('automatic_captions') or {}
    keys = list(tracks)
    if not keys: raise RuntimeError('No yt-dlp captions')
    key = language if language != 'auto' and language in tracks else next((k for k in ('en', 'zh-Hans', 'zh-Hant', 'zh-CN', 'zh-TW') if k in tracks), keys[0])
    choices = sorted(tracks[key], key=lambda x: (x.get('ext') not in ('vtt', 'srv3', 'json3'), x.get('ext', '')))
    sub = urlopen(UrlRequest(choices[0]['url'], headers={'User-Agent': 'Mozilla/5.0'}), timeout=20).read().decode('utf-8', 'ignore')
    items = []
    for block in re.split(r'\n\s*\n', sub):
        m = re.search(r'(\d{2}:\d{2}:\d{2}\.\d+)\s+-->\s+(\d{2}:\d{2}:\d{2}\.\d+)', block)
        if not m: continue
        text = re.sub(r'<[^>]+>', '', '\n'.join(block.splitlines()[2:])).strip()
        if text:
            def sec(v):
                h,mn,s=v.split(':'); return int(h)*3600+int(mn)*60+float(s)
            start,end=sec(m.group(1)),sec(m.group(2)); items.append({'text':unescape(text), 'start':start, 'duration':end-start})
    if not items: raise RuntimeError('yt-dlp subtitle was empty')
    return items, key, keys

def get_items(vid: str, language: str):
    if not YouTubeTranscriptApi: raise HTTPException(503, 'Transcript dependency is unavailable. Run install.ps1.')
    try:
        api = YouTubeTranscriptApi()
        tracks = list(api.list(vid))
        if not tracks: raise RuntimeError('No caption tracks')
        if language == 'auto':
            preferred = next((t for t in tracks if t.language_code in ('en', 'zh-Hans', 'zh-Hant')), tracks[0])
        else:
            preferred = next((t for t in tracks if t.language_code == language), None)
            if preferred is None: raise RuntimeError('Requested language is unavailable')
        fetched = preferred.fetch()
        return [{'text': x.text, 'start': x.start, 'duration': x.duration} for x in fetched], preferred.language_code, [t.language_code for t in tracks]
    except Exception:
        try:
            api = YouTubeTranscriptApi()
            fetched = api.fetch(vid, languages=[language] if language != 'auto' else ['en', 'zh-Hans', 'zh-Hant'])
            return [{'text': x.text, 'start': x.start, 'duration': x.duration} for x in fetched], getattr(fetched, 'language_code', language), []
        except Exception:
            try:
                return direct_caption_fallback(vid, language)
            except Exception:
                try:
                    return ytdlp_caption_fallback(vid, language)
                except Exception:
                    raise HTTPException(404, 'No accessible transcript was found. Check the URL, captions, or try an authorised local audio file.')

@app.post('/api/extract')
def extract(req: ExtractRequest):
    vid = video_id(req.url)
    items, lang, available = get_items(vid, req.language)
    original = '\n'.join(i['text'] for i in items)
    display = '\n\n'.join(clean_text(i['text'], lang, req.remove_fillers) for i in items) if req.add_paragraphs else ' '.join(clean_text(i['text'], lang, req.remove_fillers) for i in items)
    if req.include_timestamps:
        display = '\n'.join(f'[{timestamp(i["start"])}] {clean_text(i["text"], lang, req.remove_fillers)}' for i in items)
    return {'video_id': vid, 'video_url': f'https://www.youtube.com/watch?v={vid}', 'title': 'Transcript ready', 'channel': 'YouTube', 'thumbnail': f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg', 'language': lang, 'available_languages': available, 'items': items, 'original': original, 'transcript': display, 'word_count': len(display.split())}

@app.post('/api/transcribe-local')
async def transcribe_local(request: Request):
    try:
        from faster_whisper import WhisperModel
    except ImportError: raise HTTPException(503, 'Optional faster-whisper is not installed. Subtitles remain fully available.')
    data = await request.body(); temp = Path('backend') / '.upload-local-audio'
    temp.write_bytes(data)
    try:
        model = WhisperModel('small', device='auto', compute_type='int8')
        segments, info = model.transcribe(str(temp))
        items = [{'text': s.text.strip(), 'start': s.start, 'duration': s.end-s.start} for s in segments]
        return {'language': info.language, 'items': items, 'original': '\n'.join(x['text'] for x in items), 'transcript': '\n\n'.join(x['text'] for x in items), 'word_count': sum(len(x['text'].split()) for x in items)}
    finally:
        temp.unlink(missing_ok=True)

@app.get('/api/health')
def health(): return {'ok': True}

frontend = Path(__file__).parent.parent / 'frontend' / 'dist'
if frontend.exists(): app.mount('/', StaticFiles(directory=frontend, html=True), name='frontend')

