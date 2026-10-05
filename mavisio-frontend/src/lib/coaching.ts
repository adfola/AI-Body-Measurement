import type { WsMessage } from "../types";

const coachingMessages: Record<string, string> = {
  full_body_not_visible: "Keep your whole body visible, from head to feet.",
  step_closer: "Move a little closer to the camera.",
  step_back: "Move back a little.",
  frame_cut_off: "Keep your full body inside the frame.",
  adjust_arms: "Hold your arms slightly away from your body.",
};

export type Tone = "info" | "warn" | "good";

export function describe(message: WsMessage | null): { text: string; tone: Tone } {
  if (!message) return { text: "Connecting to the camera service...", tone: "info" };
  switch (message.status) {
    case "coaching":
      return {
        text: (message.coaching ?? []).map((code) => coachingMessages[code] ?? code).join(" "),
        tone: "warn",
      };
    case "bad_pose":
      return { text: "Stand evenly and face the camera.", tone: "warn" };
    case "calibrating":
      return { text: `Hold still while calibrating · ${Math.round((message.progress ?? 0) * 100)}%`, tone: "info" };
    case "recalibrate":
      return { text: "Calibration failed. Check the entered height and try again.", tone: "warn" };
    case "ok":
      return { text: "Pose looks good. Capture when you are ready.", tone: "good" };
    case "started":
      return { text: "Camera connected. Step into the guide to begin.", tone: "info" };
    case "captured":
      return { text: `${message.view === "side" ? "Side" : "Front"} view captured.`, tone: "good" };
    case "not_ready":
      return { text: "Hold still a moment, then capture again.", tone: "warn" };
    case "saved":
      return { text: "Measurements saved to this customer's history.", tone: "good" };
    case "error":
      return { text: `Unable to continue: ${message.reason ?? "unknown error"}.`, tone: "warn" };
  }
}
