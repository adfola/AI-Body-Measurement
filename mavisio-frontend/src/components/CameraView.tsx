import { Camera, ScanLine, SwitchCamera } from "lucide-react";
import { useEffect, useState, type RefObject } from "react";
import AlertMessage from "./AlertMessage";
import { Button } from "./ui/button";

export default function CameraView({
  videoRef,
  active,
  facingMode,
  onSwitchCamera,
}: {
  videoRef: RefObject<HTMLVideoElement | null>;
  active: boolean;
  facingMode: "user" | "environment";
  onSwitchCamera: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    if (!active) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Camera access requires localhost or a secure HTTPS connection.");
      return;
    }
    let stream: MediaStream | null = null;
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { exact: facingMode }, width: { ideal: 640 } }, audio: false })
      .then((media) => {
        if (cancelled) {
          media.getTracks().forEach((track) => track.stop());
          return;
        }
        stream = media;
        if (videoRef.current) videoRef.current.srcObject = media;
      })
      .catch(() => {
        if (!cancelled) setError("Camera access was denied or is unavailable. Allow camera access and try again.");
      });
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((track) => track.stop());
      if (videoRef.current) videoRef.current.srcObject = null;
    };
  }, [active, facingMode, videoRef]);

  if (error) {
    return (
      <div className="camera-error">
        <Camera size={22} />
        <AlertMessage>{error}</AlertMessage>
        <Button type="button" variant="outline" size="sm" onClick={onSwitchCamera}>
          <SwitchCamera size={15} /> Try the other camera
        </Button>
      </div>
    );
  }

  return (
    <div className="camera-stage">
      <video
        ref={videoRef}
        className={facingMode === "user" ? "front-camera" : "back-camera"}
        autoPlay
        muted
        playsInline
        aria-label={`Live ${facingMode === "user" ? "front" : "back"} camera`}
      />
      <div className="camera-vignette" />
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="camera-switch"
        onClick={onSwitchCamera}
        aria-label={`Switch to ${facingMode === "user" ? "back" : "front"} camera`}
        title={`Switch to ${facingMode === "user" ? "back" : "front"} camera`}
      >
        <SwitchCamera size={16} />
        {facingMode === "user" ? "Back camera" : "Front camera"}
      </Button>
      <div className="body-guide"><ScanLine size={17} /><span>FULL BODY</span></div>
      <div className="camera-corner corner-tl" />
      <div className="camera-corner corner-tr" />
      <div className="camera-corner corner-bl" />
      <div className="camera-corner corner-br" />
      <div className="camera-footer"><span className="record-dot" /> LIVE CAMERA <span>·</span> UNMIRRORED CAPTURE</div>
    </div>
  );
}
