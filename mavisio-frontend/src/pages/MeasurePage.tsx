import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Check, CircleHelp, LoaderCircle, Save, ShieldCheck } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import CameraView from "../components/CameraView";
import CoachingBanner from "../components/CoachingBanner";
import LoadingState from "../components/LoadingState";
import MeasurementTable from "../components/MeasurementTable";
import PageHeading from "../components/PageHeading";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { useMeasurement } from "../hooks/useMeasurement";
import type { Customer } from "../types";

type Step = "intro" | "front" | "side" | "review";

export default function MeasurePage() {
  const { id = "" } = useParams();
  const { token } = useAuth();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [step, setStep] = useState<Step>("intro");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.customer(id).then(setCustomer).catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : "Could not load this client.");
    }).finally(() => setLoading(false));
  }, [id]);

  const { result, connected, socketError, startView, capture, save } = useMeasurement(
    videoRef,
    token ?? "",
    id,
    customer?.height_cm ?? 0,
    step !== "intro" && !!customer?.height_cm,
  );

  useEffect(() => {
    if (result?.status !== "captured") return;
    if (step === "front") {
      setStep("side");
      startView("side");
    } else if (step === "side") {
      setStep("review");
    }
  }, [result, startView, step]);

  if (loading) return <LoadingState label="Loading client profile" />;
  if (error) return <div className="page-stack"><Link className="back-link" to="/dashboard"><ArrowLeft size={15} /> Clients</Link><div className="inline-error">{error}</div></div>;
  if (!customer) return null;

  if (step === "intro") {
    return (
      <div className="page-stack">
        <Link className="back-link" to="/dashboard"><ArrowLeft size={15} /> All clients</Link>
        <PageHeading eyebrow="MEASUREMENT SESSION" title={`Measure ${customer.full_name}`} description="A guided two-view capture for a more considered fit." />
        <div className="capture-intro-grid">
          <Card className="capture-prep">
            <div className="prep-heading"><span className="prep-number">01</span><div><div className="section-index">BEFORE YOU BEGIN</div><h2>Prepare the fitting</h2></div></div>
            <ul className="prep-list">
              <li><Check size={16} /> Fitted clothing, hair clear of neck and shoulders.</li>
              <li><Check size={16} /> Camera steady at chest height, full body in frame.</li>
              <li><Check size={16} /> Even light with a clear, uncluttered background.</li>
              <li><Check size={16} /> Front pose first, then turn 90° to the right.</li>
            </ul>
            <div className="height-calibration"><span>CALIBRATION HEIGHT</span><strong>{customer.height_cm ? `${customer.height_cm} cm` : "Not set"}</strong></div>
          </Card>
          <div className="capture-side-note"><div className="side-note-icon"><CircleHelp size={19} /></div><span className="section-index">A NOTE ON ACCURACY</span><p>Camera-based measurements are estimates. Fitted clothing and a relaxed, steady pose help improve consistency.</p><span className="note-rule" /><span className="section-index">FRONT + SIDE</span><p>Two silhouettes are used to estimate bust, waist, and hip circumference.</p></div>
        </div>
        {!customer.height_cm && <div className="inline-error">Add a height between 100 and 230 cm to calibrate this session.</div>}
        <Button size="lg" className="begin-button" onClick={() => setStep("front")} disabled={!customer.height_cm}>Open camera <ArrowRight size={17} /></Button>
      </div>
    );
  }

  const isCaptureStep = step === "front" || step === "side";
  const isSaved = result?.status === "saved";
  const canCapture = isCaptureStep && result?.status === "ok" && result.view === step;
  const rows = Object.entries(result?.measurements ?? {}).map(([name, value_cm]) => ({ name, value_cm }));

  return (
    <div className="page-stack measure-page">
      <Link className="back-link" to="/dashboard"><ArrowLeft size={15} /> All clients</Link>
      <PageHeading
        eyebrow={`MEASUREMENT SESSION · ${customer.full_name.toUpperCase()}`}
        title={step === "front" ? "Front view" : step === "side" ? "Side view" : "Review measurements"}
        description={step === "side" ? "Turn 90° to your right; keep arms relaxed and slightly forward." : step === "front" ? "Face the camera and hold a relaxed A-pose." : "Review the saved session for this client."}
        action={<span className={`connection-pill ${connected ? "online" : "offline"}`}><i /> {connected ? "SERVICE CONNECTED" : "CONNECTING"}</span>}
      />
      <div className="capture-progress" aria-label="Capture progress">
        {["Front", "Side", "Review"].map((label, index) => {
          const activeIndex = step === "front" ? 0 : step === "side" ? 1 : 2;
          return <div className={`progress-step ${index < activeIndex ? "complete" : index === activeIndex ? "active" : ""}`} key={label}><span>{index < activeIndex ? <Check size={13} /> : `0${index + 1}`}</span>{label}</div>;
        })}
      </div>
      <div className="capture-workspace">
        <section className="camera-column">
          {!isSaved && step !== "review" && <CameraView videoRef={videoRef} active={isCaptureStep} />}
          {step === "review" && !isSaved && <div className="review-ready"><ShieldCheck size={23} /><strong>Both views captured</strong><span>Save the measurement session to the client record.</span></div>}
          <CoachingBanner msg={socketError ? { status: "error", reason: socketError } : result} />
          {socketError && <div className="inline-error" role="alert">{socketError}</div>}
          {!connected && !socketError && <div className="connection-hint"><LoaderCircle className="spin" size={15} /> Connecting to measurement service</div>}
          {isCaptureStep && <Button size="lg" className="capture-button" onClick={capture} disabled={!canCapture}><span className="capture-button-dot" /> Capture {step} view</Button>}
          {step === "review" && !isSaved && <Button size="lg" className="capture-button" onClick={save} disabled={!connected}><Save size={17} /> Save measurements</Button>}
          {isSaved && <Button asChild variant="outline" className="capture-button"><Link to={`/history/${customer.id}`}>View client history <ArrowRight size={16} /></Link></Button>}
        </section>
        <aside className="measurement-aside">
          <div className="aside-heading"><span className="section-index">SESSION DETAIL</span><span className="aside-session-mark">M</span></div>
          <div className="aside-person"><span className="client-avatar large">{customer.full_name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase()}</span><div><strong>{customer.full_name}</strong><span>{customer.height_cm} cm calibration height</span></div></div>
          <div className="aside-divider" />
          <span className="section-index">CAPTURE CHECKLIST</span>
          <div className="checklist-row"><span className={step !== "front" ? "check-complete" : "check-current"}>{step !== "front" ? <Check size={13} /> : "1"}</span><span>Front silhouette</span><small>{step === "front" ? "IN PROGRESS" : "CAPTURED"}</small></div>
          <div className="checklist-row"><span className={step === "review" ? "check-complete" : step === "side" ? "check-current" : "check-pending"}>{step === "review" ? <Check size={13} /> : "2"}</span><span>Side silhouette</span><small>{step === "side" ? "IN PROGRESS" : step === "review" ? "CAPTURED" : "PENDING"}</small></div>
          <div className="aside-divider" />
          <span className="section-index">LIVE MEASUREMENTS</span>
          {isSaved ? <MeasurementTable items={rows} /> : <p className="measurements-placeholder">Measurements appear here after both views have been saved.</p>}
          <div className="aside-secure"><ShieldCheck size={14} /> Frames are processed live, not stored.</div>
        </aside>
      </div>
    </div>
  );
}
