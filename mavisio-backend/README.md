# Mavisio Backend

FastAPI REST and WebSocket service for a tailor-owned customer directory and guided two-view body measurement. The API is available at `http://localhost:8000`; Swagger UI is at `http://localhost:8000/docs`.

## Local development on Windows (without Docker)

Prerequisites: Python 3.11 and a local PostgreSQL server listening on `localhost:5432`. Create a PostgreSQL login named `mavisio` and a database named `mavisio` owned by that login. Set the matching password in `.env`; the `POSTGRES_*` values in `.env` do not create a role or database on a locally installed PostgreSQL server.

From PowerShell, run:

```powershell
cd C:\Users\FOLARIN\Documents\GitHub\AI-Body-Measurement\mavisio-backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --workers 1
```

Open `http://localhost:8000/docs` or check `GET http://localhost:8000/api/v1/health`. API routes are rooted at `/api/v1`; the authenticated measurement WebSocket is `ws://localhost:8000/ws/measurement`. Start the command from this directory so `.env` is loaded. `.env` and `.env.docker` are local-only; use `.env.example` as the variable reference and never share real secrets.

## API workflow in Postman

Set `baseUrl` to `http://localhost:8000`.

1. `GET {{baseUrl}}/api/v1/health` should return `200` and `{"status":"ok"}` when PostgreSQL is reachable.
2. `POST {{baseUrl}}/api/v1/auth/register` with JSON `{"email":"tailor@example.com","password":"test-password-123"}` creates an account. Repeated registration returns `409`.
3. `POST {{baseUrl}}/api/v1/auth/login` with body type `x-www-form-urlencoded`, fields `username=tailor@example.com` and `password=test-password-123`, returns a bearer token. Save `access_token` as `token`.
4. Call `GET {{baseUrl}}/api/v1/auth/me` with Authorization type `Bearer Token` and `{{token}}`; it should return the account id and email.
5. `POST {{baseUrl}}/api/v1/customers` with the bearer token and JSON `{"full_name":"Test Client","height_cm":165}` creates a customer. Save its `id` as `customerId`.
6. `GET {{baseUrl}}/api/v1/customers`, `GET {{baseUrl}}/api/v1/customers/{{customerId}}`, and `DELETE {{baseUrl}}/api/v1/customers/{{customerId}}` exercise customer list, read, and delete. Deleting returns `204`.
7. `GET {{baseUrl}}/api/v1/measurements/customers/{{customerId}}/sessions` lists saved sessions; `GET {{baseUrl}}/api/v1/measurements/sessions/{{sessionId}}` reads one session.

The measurement WebSocket is not a REST request: connect to `ws://localhost:8000/ws/measurement`, send `{"type":"auth","token":"<token>"}` first, then `start` with the customer id, height, and `front` view. Send base64 JPEG `image` messages, then `capture`; repeat `start` for `side`, send frames, and capture again. Send `save` only after both captures. Successful responses include `started`, `ok`/coaching updates, `captured`, and finally `saved`. Invalid auth closes the socket with policy code `1008`.

## Vertical scaling

This service deliberately runs a single Uvicorn worker per container. MediaPipe and YOLO are memory-heavy, the detector is loaded once, and inference is serialized because the pose instance is not thread-safe. Scale up the host/container's CPU and RAM, then tune `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `DB_POOL_SIZE`, and `DB_MAX_OVERFLOW` in line with that machine. Keep latest-frame-only processing and one frame in flight per browser. Avoid increasing worker count on a small host: it duplicates model memory and does not make a single camera stream more accurate. PostgreSQL data is on the named `postgres_data` volume.

For a larger production deployment, terminate TLS at the reverse proxy, allow only the deployed frontend origin, move secrets into the host secret manager, and run one inference process per available machine-sized replica behind a WebSocket-aware load balancer with session affinity.

## Render deployment

The repository-root `render.yaml` defines the Docker web service and a managed PostgreSQL database. Review the instance and database plans before creating the Blueprint; the defaults are paid Render resources. Render runs Alembic once as the pre-deploy command, then starts one Uvicorn worker per container so model memory is not duplicated. Render's `PORT` is used automatically.

The Blueprint generates `JWT_SECRET`, sets the production CORS origin to the live Vercel frontend, and configures a small database pool per replica. To connect the frontend, set Vercel's `VITE_API_URL` to the Render service's HTTPS origin and redeploy. `VITE_WS_URL` can be set to override the corresponding `wss://<service>/ws/measurement` URL.

## Checks

Run `pytest -v` from this directory. Unit tests for the geometry/filter pipeline do not need PostgreSQL. The WebSocket authentication test does not start the model or database. Real registration, customer CRUD, and measurement persistence require the Compose services to be running.
