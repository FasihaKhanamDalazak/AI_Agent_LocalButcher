/** Sender roles used to distinguish message alignment/styling. */
export const MESSAGE_ROLES = {
  USER: "user",
  ASSISTANT: "assistant",
};

/** How long a request must be pending before we show the "waking up" copy. */
export const SLOW_RESPONSE_THRESHOLD_MS = 8000;

/** Render free-tier cold start can take this long — shown once, up front. */
export const COLD_START_HINT_MS = 6000;

/**
 * Mirrors the seeded order_statuses rows (backend/migrations) in display
 * order — used by the staff dashboard's status-change dropdown. Kept as a
 * plain list here rather than fetched from the API since these are fixed
 * reference data the backend itself treats as static seed rows, not
 * something that changes at runtime.
 */
export const ORDER_STATUS_OPTIONS = [
  { code: "pending", label: "Pending" },
  { code: "confirmed", label: "Confirmed" },
  { code: "packed", label: "Packed" },
  { code: "out_for_delivery", label: "Out for delivery" },
  { code: "delivered", label: "Delivered" },
  { code: "cancelled", label: "Cancelled" },
];
