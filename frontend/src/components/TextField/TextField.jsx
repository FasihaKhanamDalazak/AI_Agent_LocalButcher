/**
 * Consistent labeled input used across auth and the address forms.
 * Forwards any extra props (minLength, autoComplete, etc.) to the input.
 *
 * @param {string} label
 * @param {string} [error] - shown below the field, also switches the border red
 */
function TextField({ label, error, className = "", ...inputProps }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1.5 block text-sm font-medium text-ink">{label}</span>
      <input
        className={`
          w-full rounded-input border bg-surface px-4 py-2.5 text-base text-ink
          placeholder:text-ink-soft transition duration-200
          focus:outline-none
          ${error ? "border-error/50" : "border-line focus:border-red/50 focus:shadow-glow"}
        `}
        {...inputProps}
      />
      {error && <span className="mt-1 block text-xs text-error">{error}</span>}
    </label>
  );
}

export default TextField;
