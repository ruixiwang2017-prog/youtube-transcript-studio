# YouTube Transcript Studio

Local-first transcript extraction studio. The core path uses `youtube-transcript-api`; metadata is best-effort via `yt-dlp`. Speech recognition is intentionally opt-in and only accepts user-supplied audio.

## Run on Windows

```powershell
.\install.ps1
.\start.ps1
```

Open http://127.0.0.1:8000. To use the frontend separately, run `npm install` and `npm run dev` in `frontend`.

## Optional speech recognition

Install `faster-whisper` separately, then use the authorised local-audio endpoint exposed by the backend. No YouTube audio is downloaded automatically.

