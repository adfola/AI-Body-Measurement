import { LoaderCircle } from "lucide-react";

export default function LoadingState({ label = "Loading your workspace" }: { label?: string }) {
  return <div className="loading-state"><LoaderCircle className="spin" size={20} /><span>{label}</span></div>;
}
