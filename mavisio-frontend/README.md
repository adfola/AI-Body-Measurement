# Mavisio Frontend

Tailor-facing React application for client records, front/side camera measurement, and session history. Uses React Router, TypeScript, Tailwind CSS, shadcn-compatible UI primitives, and Lucide icons.

## Local setup

Requires Node 20+ and the backend on `http://localhost:8000`.

```powershell
npm install
npm run dev
```

Open `http://localhost:5173`. Local API and WebSocket URLs can be set in `.env`; edit those variables if the backend runs elsewhere. `.env.example` is the committed template, and `.env` is ignored. Camera access requires localhost or HTTPS.

For the Vercel deployment, set `VITE_API_URL` to the deployed backend origin (for example, `https://mavisio-api.onrender.com`). `VITE_WS_URL` is optional; when omitted, the frontend derives the secure WebSocket URL from `VITE_API_URL`. Set these variables in Vercel and redeploy after the Render service is available.

## Checks

```powershell
npm test
npm run lint
npm run build
```
