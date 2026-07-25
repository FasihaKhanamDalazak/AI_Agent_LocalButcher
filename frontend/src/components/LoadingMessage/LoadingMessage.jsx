import { motion } from "framer-motion";
import { ChefHat } from "lucide-react";
import TypingIndicator from "../TypingIndicator/TypingIndicator.jsx";

/**
 * Occupies the slot a real assistant reply will land in while a
 * request is in flight.
 */
function LoadingMessage() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
      className="flex items-end gap-2.5"
    >
      <span
        className="mb-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-gradient text-white shadow-sm"
        aria-hidden="true"
      >
        <ChefHat size={17} strokeWidth={2} />
      </span>

      <div className="rounded-card border border-line bg-surface px-4 py-3 shadow-sm">
        <TypingIndicator />
      </div>
    </motion.div>
  );
}

export default LoadingMessage;