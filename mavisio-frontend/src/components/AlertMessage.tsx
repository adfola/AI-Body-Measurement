import { AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";

export default function AlertMessage({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`app-alert ${className}`.trim()} role="alert">
      <AlertTriangle size={17} aria-hidden="true" />
      <span>{children}</span>
    </div>
  );
}
