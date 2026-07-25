import { Children, isValidElement, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown } from "lucide-react";

/**
 * Fully custom dropdown, not a native <select> — a native <select>'s open
 * option list is rendered by the OS/browser and simply cannot be styled
 * with CSS in any browser, which is why the closed field could be themed
 * but the popup couldn't. This keeps the exact same external shape a
 * native <select> would have (`value` + `onChange({ target: { value } })`
 * + plain `<option>` children) purely so call sites didn't need to change.
 */
function Select({ label, value, onChange, className = "", children }) {
  const options = Children.toArray(children)
    .filter(isValidElement)
    .map((child) => ({ value: child.props.value, label: child.props.children }));

  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const rootRef = useRef(null);
  const listRef = useRef(null);

  const selected = options.find((o) => o.value === value);
  const selectedIndex = options.findIndex((o) => o.value === value);

  useEffect(() => {
    if (!isOpen) return;
    listRef.current?.focus();
    const handleClickOutside = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setIsOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const open = () => {
    setHighlightedIndex(selectedIndex >= 0 ? selectedIndex : 0);
    setIsOpen(true);
  };

  const commit = (val) => {
    onChange({ target: { value: val } });
    setIsOpen(false);
  };

  const handleListKeyDown = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      setIsOpen(false);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((i) => Math.min(options.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (highlightedIndex >= 0) commit(options[highlightedIndex].value);
    } else if (e.key === "Tab") {
      setIsOpen(false);
    }
  };

  return (
    <div className={`block ${className}`} ref={rootRef}>
      {label && <span className="mb-1.5 block text-sm font-medium text-ink">{label}</span>}

      <div className="relative">
        <button
          type="button"
          onClick={() => (isOpen ? setIsOpen(false) : open())}
          onKeyDown={(e) => {
            if (!isOpen && (e.key === "Enter" || e.key === " " || e.key === "ArrowDown")) {
              e.preventDefault();
              open();
            }
          }}
          aria-haspopup="listbox"
          aria-expanded={isOpen}
          className={`
            flex w-full items-center justify-between gap-2 rounded-input border bg-surface
            px-4 py-2.5 text-left text-sm text-ink transition duration-200
            focus:outline-none
            ${isOpen ? "border-red/50 shadow-glow" : "border-line hover:border-red/30"}
          `}
        >
          <span className="truncate">{selected?.label}</span>
          <ChevronDown
            size={16}
            strokeWidth={2}
            className={`shrink-0 text-ink-soft transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
          />
        </button>

        <AnimatePresence>
          {isOpen && (
            <motion.ul
              ref={listRef}
              initial={{ opacity: 0, y: -4, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -4, scale: 0.98 }}
              transition={{ duration: 0.15 }}
              role="listbox"
              tabIndex={-1}
              onKeyDown={handleListKeyDown}
              className="
                scrollbar-elegant absolute z-30 mt-1.5 max-h-56 w-full overflow-y-auto
                rounded-card-sm border border-line bg-surface p-1.5 shadow-card
                focus:outline-none
              "
            >
              {options.map((option, index) => (
                <li
                  key={option.value}
                  role="option"
                  aria-selected={option.value === value}
                  onMouseEnter={() => setHighlightedIndex(index)}
                  onClick={() => commit(option.value)}
                  className={`
                    flex cursor-pointer items-center justify-between gap-2 rounded-card-sm px-3 py-2 text-sm transition
                    ${index === highlightedIndex ? "bg-red/[0.08] text-red" : "text-ink"}
                  `}
                >
                  <span className="truncate">{option.label}</span>
                  {option.value === value && <Check size={14} strokeWidth={2.5} className="shrink-0 text-red" />}
                </li>
              ))}
            </motion.ul>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default Select;
