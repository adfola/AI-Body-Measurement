import { ArrowRight, Eye, EyeOff, Scissors, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import AlertMessage from "../components/AlertMessage";
import { useToast } from "../components/ToastProvider";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";

export default function LoginPage() {
  const { token, login, register } = useAuth();
  const { notify } = useToast();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  if (token) return <Navigate to="/dashboard" replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") {
        await login(email, password);
        notify("Welcome back. You are signed in.", "success");
      } else {
        await register(email, password);
        notify("Your account is ready. You are signed in.", "success");
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "We could not complete that request.";
      setError(message);
      notify(message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-screen">
      <section className="auth-visual">
        <div className="auth-brand"><span className="brand-mark"><Scissors size={19} /></span><strong>MAVISIO</strong></div>
        <div className="visual-copy">
          <span className="visual-kicker"><i /> PRECISION, MADE PERSONAL</span>
          <h1>Fit begins<br />with <em>understanding.</em></h1>
          <p>A thoughtful measurement studio for the people and craft behind every great fit.</p>
        </div>
        <div className="visual-index"><span>01</span><span className="index-line" /><span>BODY MEASUREMENT STUDIO</span></div>
        <div className="visual-seal"><Scissors size={22} /><span>MADE FOR<br />THE CRAFT</span></div>
      </section>
      <section className="auth-panel">
        <div className="auth-form-wrap">
          <span className="eyebrow">TAILOR WORKSPACE</span>
          <h2>{mode === "login" ? "Welcome back" : "Create your workspace"}</h2>
          <p className="auth-subtitle">{mode === "login" ? "Sign in to continue to your measurement studio." : "Set up your account to begin measuring with Mavisio."}</p>
          <form onSubmit={submit} className="auth-form">
            <label htmlFor="email">Email address</label>
            <Input id="email" type="email" autoComplete="email" placeholder="you@atelier.com" value={email} onChange={(event) => setEmail(event.target.value)} required />
            <label htmlFor="password">Password</label>
            <div className="password-field">
              <Input id="password" type={showPassword ? "text" : "password"} autoComplete={mode === "login" ? "current-password" : "new-password"} placeholder="At least 8 characters" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required />
              <button type="button" className="password-toggle" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((value) => !value)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button>
            </div>
            {error && <AlertMessage className="form-error">{error}</AlertMessage>}
            <Button className="auth-submit" size="lg" disabled={busy}>
              {busy ? "Please wait..." : mode === "login" ? "Sign in to studio" : "Create account"}<ArrowRight size={17} />
            </Button>
          </form>
          <div className="auth-switch">
            {mode === "login" ? "New to Mavisio?" : "Already have a workspace?"}
            <button onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}>
              {mode === "login" ? "Create an account" : "Sign in"}
            </button>
          </div>
          <div className="secure-note"><ShieldCheck size={16} /><span>Your customer data stays private to your account.</span></div>
        </div>
        <footer className="auth-footer"><span>MAVISIO STUDIO · TAILOR WORKSPACE</span><span>v1.0</span></footer>
      </section>
    </main>
  );
}
