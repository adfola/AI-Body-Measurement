import { AlertCircle, CheckCircle2, Info } from "lucide-react";
import { describe } from "../lib/coaching";
import type { WsMessage } from "../types";

export default function CoachingBanner({ msg }: { msg: WsMessage | null }) {
  const { text, tone } = describe(msg);
  const Icon = tone === "good" ? CheckCircle2 : tone === "warn" ? AlertCircle : Info;
  return (
    <div className={`coaching-banner ${tone}`} role="status" aria-live="polite">
      <Icon size={18} /> <span>{text}</span>
      {msg?.status === "calibrating" && (
        <span className="calibration-track"><span style={{ width: `${Math.round((msg.progress ?? 0) * 100)}%` }} /></span>
      )}
    </div>
  );
}
