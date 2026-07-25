import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

const SIDE_POSITION = {
  top: "bottom-full left-1/2 mb-2 -translate-x-1/2",
  bottom: "top-full left-1/2 mt-2 -translate-x-1/2",
  left: "right-full top-1/2 mr-2 -translate-y-1/2",
  right: "left-full top-1/2 ml-2 -translate-y-1/2",
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
 */
function Tooltip({ label, side = "top", children }) {
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
              ${SIDE_POSITION[side]}
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
