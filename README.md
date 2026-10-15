# Mavisio AI Body Measurement

Mavisio is a tailor-facing measurement studio for managing customer profiles, guiding front-and-side camera capture, and keeping measurement history. The browser streams camera frames to a local FastAPI computer-vision service; the backend calibrates from entered height, applies capture-quality checks, estimates linear measurements and two-view circumferences, then stores only the final measurements in PostgreSQL.

## Applications

- `mavisio-backend/`: FastAPI, PostgreSQL, Alembic, authenticated REST and WebSocket services. Local API: `http://localhost:8000`.
- `mavisio-frontend/`: React, TypeScript, React Router, Tailwind, shadcn-compatible components, and Lucide. Local UI: `http://localhost:5173`.

## Start

Start Docker Desktop, open a terminal in `mavisio-backend`, and run `docker compose up --build`. Compose starts PostgreSQL, applies the migration, and serves the API. In another terminal, run `npm install` and `npm run dev` from `mavisio-frontend`. Open `http://localhost:5173`.

For Render, review and deploy the repository-root `render.yaml` Blueprint. After the backend is live, set `VITE_API_URL` in the Vercel project to the Render service's HTTPS origin and redeploy the frontend. `VITE_WS_URL` is optional; it is derived from the API URL when omitted. The Blueprint provisions paid Render resources, so review its service and database plans before deploying.

Both applications have ignored local `.env` files and committed `.env.example` templates. Keep real keys and credentials out of Git. For setup details and the vertical-scaling approach, see the README in each application.

## Measurement limitations

Camera-derived measurements are estimates affected by clothing, posture, lighting, and camera placement. Validate the outputs against tape measurements before using them for garment production.
