import { Camera, ScanLine } from "lucide-react";
import { useEffect, useState, type RefObject } from "react";

export default function CameraView({
  videoRef,
  active,
}: {
  videoRef: RefObject<HTMLVideoElement | null>;
  active: boolean;
}) {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!active) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Camera access requires localhost or a secure HTTPS connection.");
      return;
    }
    let stream: MediaStream | null = null;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "user", width: { ideal: 640 } }, audio: false })
      .then((media) => {
        stream = media;
        if (videoRef.current) videoRef.current.srcObject = media;
      })
      .catch(() => setError("Camera access was denied or is unavailable. Allow camera access and try again."));
    return () => {
      stream?.getTracks().forEach((track) => track.stop());
      if (videoRef.current) videoRef.current.srcObject = null;
    };
  }, [active, videoRef]);

  if (error) {
    return <div className="camera-error"><Camera size={22} /><p>{error}</p></div>;
  }

  return (
    <div className="camera-stage">
      <video ref={videoRef} autoPlay muted playsInline aria-label="Live measurement camera" />
      <div className="camera-vignette" />
      <div className="body-guide"><ScanLine size={17} /><span>FULL BODY</span></div>
      <div className="camera-corner corner-tl" />
      <div className="camera-corner corner-tr" />
      <div className="camera-corner corner-bl" />
      <div className="camera-corner corner-br" />
      <div className="camera-footer"><span className="record-dot" /> LIVE CAMERA <span>·</span> UNMIRRORED CAPTURE</div>
    </div>
  );
}
