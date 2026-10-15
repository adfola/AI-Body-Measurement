import { Ruler } from "lucide-react";
import type { Measurement } from "../types";

const labels: Record<string, string> = {
  shoulder_width: "Shoulder width",
  back_width: "Back width",
  sleeve: "Sleeve length",
  upper_arm: "Upper arm length",
  half_length: "Half length",
  blouse_length: "Blouse length",
  skirt_length: "Skirt length",
  bustier_length: "Bustier length",
  full_length: "Full body length",
  torso: "Torso length",
  inseam: "Inseam",
  bust: "Bust circumference",
  empire: "Empire (Underbust)",
  waist: "Waist circumference",
  hip: "Hip circumference",
  round_sleeve: "Round sleeve",
  nipple_distance: "Bust point distance",
  shoulder_to_nipple: "Shoulder to bust point",
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
          <strong>
            {measurement.value_cm.toFixed(1)}{" "}
            <small>cm · {(measurement.value_inches ?? measurement.value_cm / 2.54).toFixed(1)} in</small>
          </strong>
        </div>
      ))}
    </div>
  );
}
