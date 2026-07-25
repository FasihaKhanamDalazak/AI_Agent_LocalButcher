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

const httpClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 30000,
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
    }
    return Promise.reject(error);
  }
);

export default httpClient;
