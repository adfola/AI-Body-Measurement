export const API_URL = import.meta.env.VITE_API_URL ?? "";
export const WS_URL =
  import.meta.env.VITE_WS_URL ||
  `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/measurement`;
