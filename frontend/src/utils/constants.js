/** Sender roles used to distinguish message alignment/styling. */
export const MESSAGE_ROLES = {
  USER: "user",
  ASSISTANT: "assistant",
};

/**
 * Starter chips shown on first open, before the user has typed anything.
 * Picked to demo the assistant's actual range — shopping/recommendations,
 * order tracking, reorder, and general support — not just FAQ answers.
 */
export const STARTER_CHIPS = [
  "Update my default address",
  "Where's my order?",
  "Reorder what I got last time",
  "Raise a complaint about my order",
];

/** How long a request must be pending before we show the "waking up" copy. */
export const SLOW_RESPONSE_THRESHOLD_MS = 8000;

/** Render free-tier cold start can take this long — shown once, up front. */
export const COLD_START_HINT_MS = 6000;
