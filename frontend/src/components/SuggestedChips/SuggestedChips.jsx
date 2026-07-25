/**
 * Row of rounded pill chips with a cursor-following spotlight glow.
 * Clicking a chip calls onSelect with its label — tapping a chip sends
 * that exact string as the next message, same as typing + Enter.
 *
 * @param {string[]} chips
 * @param {(label: string) => void} onSelect
 * @param {"center"|"start"} [align="center"]
 * @param {boolean} [disabled=false] - true while the conversation hasn't
 *   been established yet (greeting still in flight) — sending before then
 *   would race against the conversation_id the greeting assigns.
 */
function SuggestedChips({ chips, onSelect, align = "center", disabled = false }) {
  if (!chips?.length) return null;

  const handleMouseMove = (e) => {
    const el = e.currentTarget;
    const rect = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - rect.left}px`);
    el.style.setProperty("--my", `${e.clientY - rect.top}px`);
  };

  return (
    <div
      className={`flex flex-wrap gap-3 ${align === "start" ? "justify-start" : "justify-center"}`}
      role="group"
      aria-label="Suggested questions"
    >
      {chips.map((chip) => (
        <button
          key={chip}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(chip)}
          onMouseMove={handleMouseMove}
          className="
            spotlight
            rounded-chip border border-line bg-white
            px-5 py-2.5 text-sm font-semibold text-ink
            shadow-sm transition duration-200
            hover:-translate-y-0.5 hover:border-red/40 hover:shadow-card
            focus-visible:outline-none
            disabled:pointer-events-none disabled:opacity-50
          "
        >
          {chip}
        </button>
      ))}
    </div>
  );
}

export default SuggestedChips;
