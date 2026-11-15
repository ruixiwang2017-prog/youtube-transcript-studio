# YouTube Transcript Studio

Local-first transcript extraction studio. The core path uses `youtube-transcript-api`; metadata is best-effort via `yt-dlp`. Speech recognition is intentionally opt-in and only accepts user-supplied audio.

## Run on Windows

```powershell
.\install.ps1
.\start.ps1
```

Open http://127.0.0.1:8000. To use the frontend separately, run `npm install` and `npm run dev` in `frontend`.

## Publish with Docker

The included `Dockerfile` builds the React frontend and serves it through FastAPI. It works with Render, Railway, or any Docker-capable host. For Render, create a new Web Service from this repository; Render will detect the Dockerfile and use the service port automatically. The included `render.yaml` can also be used as a Blueprint.

The service does not need a ChatGPT API key. The optional Whisper feature remains disabled unless its extra dependency is installed.

## Recommended production architecture

For reliable YouTube access, run the FastAPI backend on Render and the Vite frontend on Vercel. Set `VITE_API_BASE` in the Vercel production environment to the Render service URL, then redeploy the frontend.

## Publish with Vercel

The project includes `vercel.json` and `api/index.py` for Vercel's Vite + FastAPI deployment. Install the Vercel CLI, run `vercel login`, then run `vercel --prod` from the project root.

## Optional speech recognition

Install `faster-whisper` separately, then use the authorised local-audio endpoint exposed by the backend. No YouTube audio is downloaded automatically.

