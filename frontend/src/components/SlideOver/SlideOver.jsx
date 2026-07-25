import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";

/**
 * Shared right-hand slide-over shell used by the Cart, Orders, Addresses,
 * and Account panels — one overlay/animation/close-button implementation
 * instead of four near-identical ones.
 *
 * @param {boolean} isOpen
 * @param {() => void} onClose
 * @param {string} title
 * @param {import("lucide-react").LucideIcon} [icon]
 * @param {import("react").ReactNode} children
 */
function SlideOver({ isOpen, onClose, title, icon: Icon, children }) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-ink/40 backdrop-blur-sm"
            aria-hidden="true"
          />

          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            className="
              fixed right-0 top-0 z-50 flex h-dvh w-full max-w-md flex-col
              border-l border-line bg-surface shadow-card-lg
            "
          >
            <div className="flex shrink-0 items-center justify-between border-b border-line px-6 py-4">
              <div className="flex items-center gap-2.5">
                {Icon && <Icon size={18} strokeWidth={2} className="text-red" />}
                <h2 className="font-display text-lg font-bold text-ink">{title}</h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="
                  flex h-9 w-9 items-center justify-center rounded-full
                  text-ink-soft transition duration-200 hover:bg-line/60 hover:text-ink
                  focus-visible:outline-none
                "
              >
                <X size={18} strokeWidth={2} />
              </button>
            </div>

            <div className="scrollbar-elegant flex-1 overflow-y-auto px-6 py-5">{children}</div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

export default SlideOver;
