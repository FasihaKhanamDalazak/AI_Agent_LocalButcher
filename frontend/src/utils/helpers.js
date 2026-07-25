/**
 * Generates a reasonably unique id for chat messages.
 * Not cryptographically unique — sufficient for React keys + local state.
 */
export function generateId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Formats a Date into a short, elegant timestamp (e.g. "10:42 AM").
 */
export function formatTimestamp(date = new Date()) {
  return date.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Matches the backend's default CURRENCY_LABEL ("Rs.") — a display-only convention, not derived from any API response. */
export function formatCurrency(amount) {
  return `Rs. ${Number(amount).toFixed(2)}`;
}

/** Formats an ISO date string into a short date + time (e.g. "22 Jul, 4:05 PM"). */
export function formatDateTime(isoString) {
  return new Date(isoString).toLocaleString([], {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}
