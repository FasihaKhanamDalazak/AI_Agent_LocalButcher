/**
 * Single source of truth for where the JWT lives in the browser
 * (localStorage — chosen so a session survives page refreshes/restarts
 * for its full 24h life, matching how the backend already works with no
 * refresh-token flow). Every other module reads/writes the token through
 * these three functions, never localStorage directly.
 */
const TOKEN_KEY = "local_butcher_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}
