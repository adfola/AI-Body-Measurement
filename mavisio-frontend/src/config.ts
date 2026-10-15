const configuredApiUrl = import.meta.env.VITE_API_URL?.trim();

export const API_URL = configuredApiUrl?.replace(/\/+$/, "") ?? "";
export const backendConfigured = import.meta.env.DEV || Boolean(configuredApiUrl);

const websocketBase = new URL(API_URL || location.origin, location.origin);
websocketBase.protocol = websocketBase.protocol === "https:" ? "wss:" : "ws:";
websocketBase.pathname = "/ws/measurement";
websocketBase.search = "";
websocketBase.hash = "";

export const WS_URL = import.meta.env.VITE_WS_URL?.trim() || websocketBase.toString();
