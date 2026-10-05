# Mavisio Frontend

Tailor-facing React application for client records, front/side camera measurement, and session history. Uses React Router, TypeScript, Tailwind CSS, shadcn-compatible UI primitives, and Lucide icons.

## Local setup

Requires Node 20+ and the backend on `http://localhost:8000`.

```powershell
npm install
npm run dev
```

Open `http://localhost:5173`. Local API and WebSocket URLs are in `.env`; edit those variables if the backend runs elsewhere. `.env.example` is the committed template, and `.env` is ignored. Camera access requires localhost or HTTPS.

## Checks

```powershell
npm test
npm run lint
npm run build
```
