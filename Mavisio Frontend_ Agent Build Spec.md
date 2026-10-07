# MAVISIO FRONTEND: AGENT BUILD SPEC

Build the frontend exactly as specified. It is deliberately simple: 4 pages, plain CSS, no UI library, no state library. Create every file listed, run every command in order, and run each VERIFY before continuing.

## 0. Rules for the agent

1. Work in a new directory `mavisio-frontend/`.
2. Do not add libraries beyond those listed (no Tailwind, no Redux, no component kits).
3. Do not change endpoint URLs or message shapes. They must match `MAVISIO_BACKEND_SPEC.md` section 11.
4. TypeScript strict mode stays on. `npm run build` must finish with zero errors.
5. Only `.env.example` is committed.

## 1. What is being built

A tailor-facing web app:

1. **Login / Register** page
2. **Customers** page: list, add (name + height), delete, buttons to Measure or view History
3. **Measure** page: webcam capture flow (front pose, then side pose), live coaching messages, save
4. **History** page: saved measurement sessions for a customer

Stack: React 18+, TypeScript, Vite, React Router 6, plain CSS. The backend does all computer vision. The browser only streams camera frames and shows results.

## 2. Prerequisites

Node 20+ and npm. The backend must be running (`http://localhost:8000`).

```bash
node --version && npm --version
```

## 3. Setup commands

```bash
npm create vite@latest mavisio-frontend -- --template react-ts
cd mavisio-frontend
npm install
npm install react-router-dom@6
npm install -D vitest
rm -f src/App.css src/index.css && rm -rf src/assets
```

If the scaffold asks questions (experimental bundler, start now), answer **No** to experimental options and do not start the dev server.

Add to `package.json` scripts (keep the existing ones): `"test": "vitest run"`.

VERIFY: `npm run build` succeeds (it may fail until the files below exist; re-run at the end).

## 4. Environment files

**`.env.example`**

```
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws/measurement
```

Create the real file: `cp .env.example .env`.

Production behind the same domain as the API: leave both empty or unset. `config.ts` then uses the current origin (relative `/api` and `ws(s)://<host>/ws/measurement`).

`.gitignore` from the Vite template already ignores `node_modules` and `dist`. Add these lines:

```
.env
.env.local
```

## 5. File tree

```
mavisio-frontend/
├── index.html                      (template; set <title>Mavisio</title>)
├── package.json  tsconfig*.json  vite.config.ts   (template, unchanged)
├── .env.example
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── styles.css
    ├── config.ts
    ├── types.ts
    ├── api/client.ts
    ├── auth/AuthContext.tsx
    ├── lib/coaching.ts
    ├── lib/coaching.test.ts
    ├── hooks/useMeasurement.ts
    ├── components/
    │   ├── ProtectedLayout.tsx
    │   ├── CameraView.tsx
    │   ├── CoachingBanner.tsx
    │   └── MeasurementTable.tsx
    └── pages/
        ├── LoginPage.tsx
        ├── CustomersPage.tsx
        ├── MeasurePage.tsx
        └── HistoryPage.tsx
```

## 6. File contents

**`src/config.ts`**

```ts
export const API_URL: string = import.meta.env.VITE_API_URL ?? "";
export const WS_URL: string =
  import.meta.env.VITE_WS_URL ||
  `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/measurement`;
```

**`src/types.ts`**

```ts
export type View = "front" | "side";

export interface Customer {
  id: string;
  full_name: string;
  height_cm: number | null;
  created_at: string;
}

export interface Measurement {
  name: string;
  value_cm: number;
}

export interface Session {
  id: string;
  customer_id: string;
  created_at: string;
  measurements: Measurement[];
}

export type WsStatus =
  | "coaching" | "bad_pose" | "calibrating" | "recalibrate"
  | "ok" | "captured" | "not_ready" | "saved" | "error";

export interface WsMessage {
  status: WsStatus;
  coaching?: string[];
  reason?: string;
  progress?: number;
  view?: View;
  measurements?: Record<string, number>;
}
```

**`src/api/client.ts`**

```ts
import { API_URL } from "../config";
import type { Customer, Session } from "../types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let token: string | null = sessionStorage.getItem("token");
export const getToken = () => token;
export function setToken(t: string | null) {
  token = t;
  if (t) sessionStorage.setItem("token", t);
  else sessionStorage.removeItem("token");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers });
  if (res.status === 401 && token) {
    setToken(null);
    window.dispatchEvent(new Event("auth:logout"));
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* keep statusText */ }
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  register: (email: string, password: string) => request<void>("/auth/register", json("POST", { email, password })),
  login: async (email: string, password: string) => {
    const body = new URLSearchParams({ username: email, password });
    const r = await request<{ access_token: string }>("/auth/login", { method: "POST", body });
    setToken(r.access_token);
  },
  customers: () => request<Customer[]>("/customers"),
  customer: (id: string) => request<Customer>(`/customers/${id}`),
  createCustomer: (c: { full_name: string; height_cm: number }) => request<Customer>("/customers", json("POST", c)),
  deleteCustomer: (id: string) => request<void>(`/customers/${id}`, { method: "DELETE" }),
  sessions: (customerId: string) => request<Session[]>(`/measurements/customers/${customerId}/sessions`),
};
```

**`src/auth/AuthContext.tsx`**

```tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "../api/client";

interface AuthValue {
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthValue>(null!);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTok] = useState<string | null>(getToken());

  useEffect(() => {
    const onLogout = () => setTok(null);
    window.addEventListener("auth:logout", onLogout);
    return () => window.removeEventListener("auth:logout", onLogout);
  }, []);

  const login = async (email: string, password: string) => {
    await api.login(email, password);
    setTok(getToken());
  };
  const register = async (email: string, password: string) => {
    await api.register(email, password);
    await login(email, password);
  };
  const logout = () => {
    setToken(null);
    setTok(null);
  };

  return <Ctx.Provider value={{ token, login, register, logout }}>{children}</Ctx.Provider>;
}
```

**`src/lib/coaching.ts`**

```ts
import type { WsMessage } from "../types";

const MESSAGES: Record<string, string> = {
  full_body_not_visible: "Make sure your whole body is visible, head to feet.",
  step_closer: "Step a little closer to the camera.",
  step_back: "Step back a little.",
  frame_cut_off: "Keep your whole body inside the frame.",
  adjust_arms: "Hold your arms slightly away from your body (A-pose).",
};

export type Tone = "info" | "warn" | "good";

export function describe(msg: WsMessage | null): { text: string; tone: Tone } {
  if (!msg) return { text: "Connecting to the camera service...", tone: "info" };
  switch (msg.status) {
    case "coaching":
      return { text: (msg.coaching ?? []).map((c) => MESSAGES[c] ?? c).join(" "), tone: "warn" };
    case "bad_pose":
      return { text: "Stand evenly and face the camera.", tone: "warn" };
    case "calibrating":
      return { text: `Hold still... ${Math.round((msg.progress ?? 0) * 100)}%`, tone: "info" };
    case "recalibrate":
      return { text: "Calibration failed. Check the entered height and stand still.", tone: "warn" };
    case "ok":
      return { text: "Looking good. You can capture now.", tone: "good" };
    case "captured":
      return { text: "Captured.", tone: "good" };
    case "not_ready":
      return { text: "Hold still a moment, then try again.", tone: "warn" };
    case "saved":
      return { text: "Saved.", tone: "good" };
    case "error":
      return { text: `Error: ${msg.reason ?? "unknown"}`, tone: "warn" };
  }
}
```

**`src/lib/coaching.test.ts`**

```ts
import { describe as suite, it, expect } from "vitest";
import { describe } from "./coaching";

suite("describe", () => {
  it("maps coaching codes to messages", () => {
    const r = describe({ status: "coaching", coaching: ["step_back"] });
    expect(r.text).toContain("Step back");
    expect(r.tone).toBe("warn");
  });
  it("shows calibration progress", () => {
    expect(describe({ status: "calibrating", progress: 0.5 }).text).toContain("50%");
  });
  it("handles null", () => {
    expect(describe(null).tone).toBe("info");
  });
});
```

**`src/hooks/useMeasurement.ts`**

```ts
import { useCallback, useEffect, useRef, useState } from "react";
import { WS_URL } from "../config";
import type { View, WsMessage } from "../types";

type VideoRef = { current: HTMLVideoElement | null };

export function useMeasurement(videoRef: VideoRef, token: string, customerId: string, heightCm: number, enabled: boolean) {
  const ws = useRef<WebSocket | null>(null);
  const [result, setResult] = useState<WsMessage | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    const sock = new WebSocket(WS_URL);
    ws.current = sock;
    const canvas = document.createElement("canvas");
    let waiting = false;
    let sentAt = 0;

    sock.onopen = () => {
      sock.send(JSON.stringify({ type: "auth", token }));
      sock.send(JSON.stringify({ type: "start", customer_id: customerId, height_cm: heightCm, view: "front" }));
      setConnected(true);
    };
    sock.onmessage = (e) => {
      setResult(JSON.parse(e.data) as WsMessage);
      waiting = false;
    };
    sock.onclose = () => setConnected(false);

    // ~10 FPS, 480px wide, one frame in flight (with a 1.5 s safety timeout)
    const timer = window.setInterval(() => {
      const v = videoRef.current;
      if (!v || !v.videoWidth || sock.readyState !== WebSocket.OPEN) return;
      if (waiting && Date.now() - sentAt < 1500) return;
      canvas.width = 480;
      canvas.height = Math.round((480 * v.videoHeight) / v.videoWidth);
      canvas.getContext("2d")?.drawImage(v, 0, 0, canvas.width, canvas.height);
      waiting = true;
      sentAt = Date.now();
      sock.send(JSON.stringify({ type: "image", data: canvas.toDataURL("image/jpeg", 0.7) }));
    }, 100);

    return () => {
      window.clearInterval(timer);
      sock.close();
    };
  }, [enabled, token, customerId, heightCm, videoRef]);

  const send = useCallback((m: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify(m));
  }, []);

  return {
    result,
    connected,
    startView: (view: View) => send({ type: "start", customer_id: customerId, height_cm: heightCm, view }),
    capture: () => send({ type: "capture" }),
    save: () => send({ type: "save" }),
  };
}
```

**`src/components/CameraView.tsx`**

```tsx
import { useEffect, useState } from "react";

type VideoRef = { current: HTMLVideoElement | null };

export default function CameraView({ videoRef, active }: { videoRef: VideoRef; active: boolean }) {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!active) return;
    let stream: MediaStream | null = null;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "user", width: 640 }, audio: false })
      .then((s) => {
        stream = s;
        if (videoRef.current) videoRef.current.srcObject = s;
      })
      .catch(() => setError("Camera access was denied or is unavailable. Allow camera access and use HTTPS or localhost."));
    return () => stream?.getTracks().forEach((t) => t.stop());
  }, [active, videoRef]);

  if (error) return <p className="banner warn">{error}</p>;
  return (
    <div className="camera">
      <video ref={videoRef as React.RefObject<HTMLVideoElement>} autoPlay muted playsInline />
      <div className="guide" />
    </div>
  );
}
```

**`src/components/CoachingBanner.tsx`**

```tsx
import { describe } from "../lib/coaching";
import type { WsMessage } from "../types";

export default function CoachingBanner({ msg }: { msg: WsMessage | null }) {
  const { text, tone } = describe(msg);
  return <p className={`banner ${tone}`}>{text}</p>;
}
```

**`src/components/MeasurementTable.tsx`**

```tsx
const LABELS: Record<string, string> = {
  shoulder_width: "Shoulder width", sleeve: "Sleeve length", torso: "Torso length", inseam: "Inseam",
  bust: "Bust", waist: "Waist", hip: "Hip",
};

export default function MeasurementTable({ items }: { items: { name: string; value_cm: number }[] }) {
  return (
    <table>
      <tbody>
        {items.map((m) => (
          <tr key={m.name}>
            <td>{LABELS[m.name] ?? m.name}</td>
            <td>{m.value_cm.toFixed(1)} cm</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

**`src/components/ProtectedLayout.tsx`**

```tsx
import { Link, Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function ProtectedLayout() {
  const { token, logout } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return (
    <>
      <header>
        <Link to="/"><strong>Mavisio</strong></Link>
        <button className="link" onClick={logout}>Log out</button>
      </header>
      <main><Outlet /></main>
    </>
  );
}
```

**`src/pages/LoginPage.tsx`**

```tsx
import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const { token, login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (token) return <Navigate to="/" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await (mode === "login" ? login : register)(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="narrow">
      <h1>Mavisio</h1>
      <form onSubmit={submit}>
        <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input type="password" placeholder="Password (min 8 characters)" minLength={8} value={password}
               onChange={(e) => setPassword(e.target.value)} required />
        {error && <p className="banner warn">{error}</p>}
        <button disabled={busy}>{mode === "login" ? "Log in" : "Create account"}</button>
      </form>
      <button className="link" onClick={() => setMode(mode === "login" ? "register" : "login")}>
        {mode === "login" ? "Need an account? Register" : "Have an account? Log in"}
      </button>
    </main>
  );
}
```

**`src/pages/CustomersPage.tsx`**

```tsx
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Customer } from "../types";

export default function CustomersPage() {
  const [list, setList] = useState<Customer[]>([]);
  const [name, setName] = useState("");
  const [height, setHeight] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = () => api.customers().then(setList).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.createCustomer({ full_name: name, height_cm: Number(height) });
      setName("");
      setHeight("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add customer");
    }
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this customer and all their measurements?")) return;
    await api.deleteCustomer(id);
    load();
  };

  return (
    <>
      <h2>Customers</h2>
      <form onSubmit={add} className="row">
        <input placeholder="Full name" value={name} onChange={(e) => setName(e.target.value)} required />
        <input type="number" placeholder="Height (cm)" min={100} max={230} value={height}
               onChange={(e) => setHeight(e.target.value)} required />
        <button>Add</button>
      </form>
      {error && <p className="banner warn">{error}</p>}
      <ul className="list">
        {list.map((c) => (
          <li key={c.id}>
            <span>{c.full_name} <small>{c.height_cm} cm</small></span>
            <span>
              <Link to={`/measure/${c.id}`}>Measure</Link>{" "}
              <Link to={`/history/${c.id}`}>History</Link>{" "}
              <button className="link" onClick={() => remove(c.id)}>Delete</button>
            </span>
          </li>
        ))}
        {list.length === 0 && <li>No customers yet.</li>}
      </ul>
    </>
  );
}
```

**`src/pages/MeasurePage.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useMeasurement } from "../hooks/useMeasurement";
import CameraView from "../components/CameraView";
import CoachingBanner from "../components/CoachingBanner";
import MeasurementTable from "../components/MeasurementTable";
import type { Customer } from "../types";

type Step = "intro" | "front" | "side" | "review";

export default function MeasurePage() {
  const { id = "" } = useParams();
  const { token } = useAuth();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [step, setStep] = useState<Step>("intro");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.customer(id).then(setCustomer).catch((e) => setError(e.message));
  }, [id]);

  const { result, connected, startView, capture, save } = useMeasurement(
    videoRef, token ?? "", id, customer?.height_cm ?? 0, step !== "intro" && !!customer?.height_cm,
  );

  useEffect(() => {
    if (result?.status !== "captured") return;
    if (step === "front") {
      setStep("side");
      startView("side");
    } else if (step === "side") {
      setStep("review");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  if (error) return <p className="banner warn">{error}</p>;
  if (!customer) return <p>Loading...</p>;

  if (step === "intro") {
    return (
      <>
        <h2>Measure {customer.full_name}</h2>
        <ul>
          <li>Wear fitted or tight clothing; tie hair off the neck and shoulders.</li>
          <li>Stand 2 to 3 metres from the camera, camera at chest height, plain background, good light.</li>
          <li>Whole body, head to feet, must be inside the outline.</li>
          <li>Front: face the camera, arms slightly away from your body. Side: turn 90 degrees to your right.</li>
        </ul>
        <button onClick={() => setStep("front")} disabled={!customer.height_cm}>Start camera</button>
      </>
    );
  }

  const saved = result?.status === "saved";
  const canCapture = result?.status === "ok" && result.view === step;
  const rows = Object.entries(result?.measurements ?? {}).map(([name, value_cm]) => ({ name, value_cm }));

  return (
    <>
      <h2>{customer.full_name}: {step === "front" ? "Front view" : step === "side" ? "Side view (turn right)" : "Review"}</h2>
      {!saved && <CameraView videoRef={videoRef} active />}
      <CoachingBanner msg={result} />
      {!connected && <p className="banner warn">Not connected to the server.</p>}
      {(step === "front" || step === "side") && <button onClick={capture} disabled={!canCapture}>Capture {step} view</button>}
      {step === "review" && !saved && <button onClick={save} disabled={!connected}>Save measurements</button>}
      {saved && (
        <>
          <MeasurementTable items={rows} />
          <p><Link to={`/history/${id}`}>View history</Link> · <Link to="/">Back to customers</Link></p>
        </>
      )}
    </>
  );
}
```

**`src/pages/HistoryPage.tsx`**

```tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import MeasurementTable from "../components/MeasurementTable";
import type { Session } from "../types";

export default function HistoryPage() {
  const { id = "" } = useParams();
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.sessions(id).then(setSessions).catch((e) => setError(e.message));
  }, [id]);

  if (error) return <p className="banner warn">{error}</p>;
  if (!sessions) return <p>Loading...</p>;
  return (
    <>
      <h2>Measurement history</h2>
      <p><Link to="/">Back</Link></p>
      {sessions.length === 0 && <p>No saved sessions yet.</p>}
      {sessions.map((s) => (
        <section key={s.id}>
          <h3>{new Date(s.created_at).toLocaleString()}</h3>
          <MeasurementTable items={s.measurements} />
        </section>
      ))}
    </>
  );
}
```

**`src/App.tsx`**

```tsx
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import ProtectedLayout from "./components/ProtectedLayout";
import LoginPage from "./pages/LoginPage";
import CustomersPage from "./pages/CustomersPage";
import MeasurePage from "./pages/MeasurePage";
import HistoryPage from "./pages/HistoryPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedLayout />}>
            <Route path="/" element={<CustomersPage />} />
            <Route path="/measure/:id" element={<MeasurePage />} />
            <Route path="/history/:id" element={<HistoryPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
```

**`src/main.tsx`**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

**`src/styles.css`**

```css
:root { font-family: system-ui, sans-serif; color: #1a1a1a; background: #fafafa; }
body { margin: 0; }
header { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1rem; background: #fff; border-bottom: 1px solid #e5e5e5; }
main { max-width: 720px; margin: 0 auto; padding: 1rem; }
main.narrow { max-width: 360px; margin-top: 4rem; }
form { display: flex; flex-direction: column; gap: 0.5rem; }
form.row { flex-direction: row; flex-wrap: wrap; }
input { padding: 0.6rem; border: 1px solid #ccc; border-radius: 6px; font-size: 1rem; }
button { padding: 0.6rem 1rem; border: 0; border-radius: 6px; background: #1a1a1a; color: #fff; font-size: 1rem; cursor: pointer; }
button:disabled { opacity: 0.4; cursor: not-allowed; }
button.link, a { background: none; color: #0b5fff; padding: 0; border: 0; cursor: pointer; text-decoration: none; }
.list { list-style: none; padding: 0; }
.list li { display: flex; justify-content: space-between; padding: 0.6rem 0; border-bottom: 1px solid #eee; }
.banner { padding: 0.6rem 0.8rem; border-radius: 6px; margin: 0.75rem 0; }
.banner.info { background: #eef3ff; }
.banner.warn { background: #fff1e6; }
.banner.good { background: #e8f7ec; }
.camera { position: relative; width: 100%; max-width: 480px; margin: 0 auto; }
.camera video { width: 100%; border-radius: 8px; background: #000; transform: scaleX(-1); }
.guide { position: absolute; inset: 4% 25%; border: 2px dashed rgba(255, 255, 255, 0.7); border-radius: 12px; pointer-events: none; }
table { width: 100%; border-collapse: collapse; margin: 0.5rem 0 1rem; }
td { padding: 0.45rem; border-bottom: 1px solid #eee; }
td:last-child { text-align: right; font-variant-numeric: tabular-nums; }
```

Set `index.html` `<title>` to `Mavisio`.

## 7. Commands

| Purpose | Command |
| --- | --- |
| Dev server | `npm run dev` (http://localhost:5173) |
| Type-check + production build | `npm run build` |
| Lint | `npm run lint` |
| Unit tests | `npm test` |
| Preview build | `npm run preview` |

## 8. Verification checklist (run in order)

1. `npm test` passes (3 tests).
2. `npm run lint` and `npm run build` finish with no errors.
3. Start the backend, then `npm run dev`. In the browser:
   - Register a new account on `/login`; you land on Customers.
   - Add a customer (name, height 165). It appears in the list.
   - Click **Measure**, **Start camera**, allow the camera. Coaching messages change as you move. After calibration shows `Hold still... 100%`, the banner turns green and **Capture front view** enables.
   - Capture front, turn to the side, capture side, click **Save measurements**. A table appears with shoulder width, sleeve, torso, inseam, bust, waist and hip.
   - Open **History**; the saved session is listed.
4. Refresh the page while logged in: you stay logged in (token in `sessionStorage`). Click **Log out**: you return to `/login`.

## 9. Deployment

The camera and `wss://` both require HTTPS in production.

**Option A: same domain as the backend (simplest).** Build and let the backend's Nginx serve it:

```bash
npm run build
cp -r dist ../mavisio-backend/frontend-dist
```

In `mavisio-backend/docker-compose.yml`, add to the `nginx` service volumes: `"./frontend-dist:/usr/share/nginx/html:ro"`. In `mavisio-backend/nginx.conf`, add inside `server { ... }`:

```nginx
  root /usr/share/nginx/html;
  location / { try_files $uri /index.html; }
```

Leave `VITE_API_URL` and `VITE_WS_URL` unset when building so the app uses relative URLs. Then `docker compose up -d`.

**Option B: static host (Vercel / Netlify).** Set build env vars `VITE_API_URL=https://api.yourdomain.com` and `VITE_WS_URL=wss://api.yourdomain.com/ws/measurement`, build command `npm run build`, output directory `dist`, and add an SPA rewrite of all paths to `/index.html`. In the backend `.env` set `CORS_ORIGINS=["https://your-frontend-domain"]`.

## 10. Definition of done

- `npm test`, `npm run lint`, `npm run build` all pass.
- The full flow in section 8 works against the real backend.
- No `.env` in git; no extra libraries beyond `react`, `react-dom`, `react-router-dom@6`, `vite`, `typescript`, `vitest` and the template's dev tooling.

## 11. Notes

- The token lives in `sessionStorage`, which survives refreshes but not closing the tab. That is acceptable here; do not move it to `localStorage`.
- Frames are sent at about 10 per second, 480 px wide, one in flight. Do not raise this; the server drops stale frames anyway.
- The mirrored video preview is cosmetic (CSS only). The frames sent to the backend are not mirrored.