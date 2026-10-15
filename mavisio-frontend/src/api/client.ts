import { API_URL, backendConfigured } from "../config";
import type { Customer, Session } from "../types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

let token: string | null = sessionStorage.getItem("mavisio.token");

export const getToken = () => token;

export function setToken(value: string | null) {
  token = value;
  if (value) sessionStorage.setItem("mavisio.token", value);
  else sessionStorage.removeItem("mavisio.token");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!backendConfigured) {
    throw new ApiError(0, "The backend is not configured. Set VITE_API_URL to your backend URL.");
  }
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers });

  if (response.status === 401 && token) {
    setToken(null);
    window.dispatchEvent(new Event("auth:logout"));
  }
  if (!response.ok) {
    let message = response.statusText || "Request failed";
    try {
      const body: unknown = await response.json();
      if (body && typeof body === "object" && "detail" in body) {
        const detail = body.detail;
        message = typeof detail === "string" ? detail : JSON.stringify(detail);
      }
    } catch {
      // Preserve status text for non-JSON responses.
    }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function json(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export const api = {
  register: (email: string, password: string) =>
    request<void>("/auth/register", json("POST", { email, password })),
  login: async (email: string, password: string) => {
    const body = new URLSearchParams({ username: email, password });
    const result = await request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body,
    });
    setToken(result.access_token);
  },
  me: () => request<{ id: string; email: string }>("/auth/me"),
  customers: () => request<Customer[]>("/customers"),
  customer: (id: string) => request<Customer>(`/customers/${id}`),
  createCustomer: (customer: { full_name: string; height_cm: number }) =>
    request<Customer>("/customers", json("POST", customer)),
  deleteCustomer: (id: string) => request<void>(`/customers/${id}`, { method: "DELETE" }),
  sessions: (customerId: string) =>
    request<Session[]>(`/measurements/customers/${customerId}/sessions`),
  session: (id: string) => request<Session>(`/measurements/sessions/${id}`),
};
