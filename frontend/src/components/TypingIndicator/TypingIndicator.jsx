import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

const WORDS = ["Thinking...", "Searching...", "Analyzing..."];

function TypingIndicator() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const wordInterval = setInterval(() => {
      setIndex((prev) => (prev + 1) % WORDS.length);
    }, 1800);

    return () => clearInterval(wordInterval);
  }, []);

  return (
    <div
      className="flex items-center justify-center h-6 w-fit min-w-[92px]"
      aria-label="Assistant is thinking"
    >
      <AnimatePresence mode="wait">
        <motion.span
          key={WORDS[index]}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="
            text-sm
            font-medium
            tracking-tight
            whitespace-nowrap

            text-transparent
            bg-clip-text
            bg-[length:200%_100%]

            bg-gradient-to-r
            from-ink-soft
            via-ink
            to-ink-soft

            animate-shimmer-fast
          "
        >
          {WORDS[index]}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}

export default TypingIndicator;