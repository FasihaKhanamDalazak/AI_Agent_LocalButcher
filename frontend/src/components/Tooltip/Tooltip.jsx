import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

// "center" (default) centers the bubble on the trigger, which overflows
// off-screen for a trigger sitting near a screen edge on a narrow
// viewport (the mic/send buttons in ChatInput, close to the right edge on
// mobile) — "end" anchors the bubble's own edge to the trigger's edge
// instead, so it only ever grows inward, never past the viewport.
const SIDE_POSITION = {
  top: { center: "bottom-full left-1/2 mb-2 -translate-x-1/2", end: "bottom-full right-0 mb-2" },
  bottom: { center: "top-full left-1/2 mt-2 -translate-x-1/2", end: "top-full right-0 mt-2" },
  left: { center: "right-full top-1/2 mr-2 -translate-y-1/2", end: "right-full top-1/2 mr-2 -translate-y-1/2" },
  right: { center: "left-full top-1/2 ml-2 -translate-y-1/2", end: "left-full top-1/2 ml-2 -translate-y-1/2" },
};

const SIDE_OFFSET = {
  top: { y: 4 },
  bottom: { y: -4 },
  left: { x: 4 },
  right: { x: -4 },
};

/**
 * Wraps a single icon-only trigger with a small on-brand label bubble on
 * hover/focus — matches the "Voice input coming soon" hint bubble's look
 * (dark ink bg, cream text) that already existed ad hoc in ChatInput,
 * generalized into one reusable piece instead of every icon button
 * re-implementing its own hover-label logic.
 *
 * @param {string} label
 * @param {"top"|"bottom"|"left"|"right"} [side="top"]
 * @param {"center"|"end"} [align="center"] - "end" for a trigger near a
 *   screen edge (see SIDE_POSITION above)
 */
function Tooltip({ label, side = "top", align = "center", children }) {
  const [isVisible, setIsVisible] = useState(false);

  if (!label) return children;

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      onFocus={() => setIsVisible(true)}
      onBlur={() => setIsVisible(false)}
    >
      {children}
      <AnimatePresence>
        {isVisible && (
          <motion.span
            role="tooltip"
            initial={{ opacity: 0, ...SIDE_OFFSET[side] }}
            animate={{ opacity: 1, x: 0, y: 0 }}
            exit={{ opacity: 0, ...SIDE_OFFSET[side] }}
            transition={{ duration: 0.15 }}
            className={`
              pointer-events-none absolute z-50 whitespace-nowrap rounded-card-sm
              border border-line bg-ink px-3 py-1.5 text-xs font-medium text-cream shadow-card
              ${SIDE_POSITION[side][align]}
            `}
          >
            {label}
          </motion.span>
        )}
      </AnimatePresence>
    </span>
  );
}

export default Tooltip;
