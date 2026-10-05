import { useCallback, useEffect, useRef, useState } from "react";
import { WS_URL } from "../config";
import type { View, WsMessage } from "../types";

type VideoRef = { current: HTMLVideoElement | null };

export function useMeasurement(
  videoRef: VideoRef,
  token: string,
  customerId: string,
  heightCm: number,
  enabled: boolean,
) {
  const socketRef = useRef<WebSocket | null>(null);
  const [result, setResult] = useState<WsMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const [socketError, setSocketError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !token || !customerId) return;
    const socket = new WebSocket(WS_URL);
    socketRef.current = socket;
    const canvas = document.createElement("canvas");
    let waitingForFrame = false;
    let lastFrameAt = 0;

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: "auth", token }));
      socket.send(JSON.stringify({
        type: "start",
        customer_id: customerId,
        height_cm: heightCm,
        view: "front",
      }));
      setConnected(true);
      setSocketError(null);
    };
    socket.onmessage = (event: MessageEvent<string>) => {
      try {
        const message = JSON.parse(event.data) as WsMessage;
        setResult(message);
        if (message.status !== "started") waitingForFrame = false;
      } catch {
        setSocketError("The measurement service returned an unreadable response.");
      }
    };
    socket.onerror = () => setSocketError("Cannot reach the measurement service at the configured WebSocket URL.");
    socket.onclose = () => setConnected(false);

    const timer = window.setInterval(() => {
      const video = videoRef.current;
      if (!video?.videoWidth || socket.readyState !== WebSocket.OPEN) return;
      if (waitingForFrame && Date.now() - lastFrameAt < 1500) return;
      canvas.width = 480;
      canvas.height = Math.round((480 * video.videoHeight) / video.videoWidth);
      canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
      waitingForFrame = true;
      lastFrameAt = Date.now();
      socket.send(JSON.stringify({
        type: "image",
        data: canvas.toDataURL("image/jpeg", 0.7),
      }));
    }, 100);

    return () => {
      window.clearInterval(timer);
      socket.close();
      socketRef.current = null;
      setConnected(false);
    };
  }, [enabled, token, customerId, heightCm, videoRef]);

  const send = useCallback((message: object) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(message));
    }
  }, []);

  const startView = useCallback((view: View) => {
    setResult({ status: "started", view });
    send({ type: "start", customer_id: customerId, height_cm: heightCm, view });
  }, [customerId, heightCm, send]);

  return {
    result,
    connected,
    socketError,
    startView,
    capture: () => send({ type: "capture" }),
    save: () => send({ type: "save" }),
  };
}
