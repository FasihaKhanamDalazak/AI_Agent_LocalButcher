import axios from "axios";
import { getToken, clearToken } from "../utils/authStorage.js";

/**
 * Base URL is never hardcoded — it comes from the environment so the same
 * build can point at local, staging, or production backends.
 * Set VITE_API_URL in your .env file (see .env.example).
 */
const API_BASE_URL = import.meta.env.VITE_API_URL;

if (!API_BASE_URL) {
  console.warn("[Local Butcher] VITE_API_URL is not set. Add it to your .env file.");
}

// Render's free tier sleeps after 15 minutes idle and can take 30-60s to
// cold-start on the next request — a real, observed cause of "Couldn't
// reach the server" errors, not a hypothetical. 30s wasn't always enough
// to cover a worst-case cold start; 60s is.
const REQUEST_TIMEOUT_MS = 60000;

const httpClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: REQUEST_TIMEOUT_MS,
  headers: {
    "Content-Type": "application/json",
  },
});

// Every authenticated request carries the JWT — set once here rather than
// per-call, so no service function has to remember to attach it.
httpClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// A single place to react to "the session is no longer valid" — registered
// by useAuth at app startup rather than imported here directly, to avoid a
// circular import between the http layer and the auth hook.
let unauthorizedHandler = null;
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

httpClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearToken();
      unauthorizedHandler?.();
      return Promise.reject(error);
    }

    // A network error (request sent, no response at all — error.response is
    // undefined but error.request exists) on a Render cold start looks
    // identical to a dropped connection. GET requests are safe to retry
    // automatically since they don't change anything; POST/PATCH/DELETE are
    // deliberately NOT auto-retried here — the original request may have
    // already reached and been applied by the server (e.g. checkout,
    // add_to_cart) before the response was lost, and silently resubmitting
    // could duplicate a real action. Those still fail, but with a clearer
    // message (see normalizeApiError) telling the customer to check and
    // try again themselves rather than the assistant guessing.
    const config = error.config;
    if (error.request && !error.response && config && config.method === "get" && !config._retriedAfterColdStart) {
      config._retriedAfterColdStart = true;
      return new Promise((resolve) => setTimeout(resolve, 1500)).then(() => httpClient(config));
    }

    return Promise.reject(error);
  }
);

export default httpClient;
