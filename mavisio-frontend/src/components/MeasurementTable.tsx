import { Ruler } from "lucide-react";
import type { Measurement } from "../types";

const labels: Record<string, string> = {
  shoulder_width: "Shoulder width",
  sleeve: "Sleeve length",
  torso: "Torso length",
  inseam: "Inseam",
  bust: "Bust",
  waist: "Waist",
  hip: "Hip",
};

export default function MeasurementTable({ items }: { items: Measurement[] }) {
  if (!items.length) {
    return <div className="empty-measurements"><Ruler size={18} /> Measurements are not available yet.</div>;
  }
  return (
    <div className="measurement-list">
      {items.map((measurement) => (
        <div className="measurement-row" key={measurement.name}>
          <span>{labels[measurement.name] ?? measurement.name.replaceAll("_", " ")}</span>
          <strong>{measurement.value_cm.toFixed(1)} <small>cm</small></strong>
        </div>
      ))}
    </div>
  );
}
