import { ChefHat } from "lucide-react";

/**
 * Small fallback for the (edge-case) moment ChatContainer renders
 * before any message exists yet.
 */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-red-gradient text-white shadow-glow">
        <ChefHat size={22} strokeWidth={2} />
      </span>
      <p className="text-sm text-ink-soft">Ask a question to get started.</p>
    </div>
  );
}

export default EmptyState;