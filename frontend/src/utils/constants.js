/** Sender roles used to distinguish message alignment/styling. */
export const MESSAGE_ROLES = {
  USER: "user",
  ASSISTANT: "assistant",
};

/** How long a request must be pending before we show the "waking up" copy. */
export const SLOW_RESPONSE_THRESHOLD_MS = 8000;

/** Render free-tier cold start can take this long — shown once, up front. */
export const COLD_START_HINT_MS = 6000;
