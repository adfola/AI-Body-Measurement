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
  value_inches?: number;
}

export interface Session {
  id: string;
  customer_id: string;
  created_at: string;
  measurements: Measurement[];
}

export type WsStatus =
  | "coaching"
  | "bad_pose"
  | "calibrating"
  | "recalibrate"
  | "ok"
  | "started"
  | "captured"
  | "not_ready"
  | "saved"
  | "error";

export interface WsMessage {
  status: WsStatus;
  coaching?: string[];
  reason?: string;
  progress?: number;
  view?: View;
  measurements?: Record<string, number>;
  measurements_inches?: Record<string, number>;
}
