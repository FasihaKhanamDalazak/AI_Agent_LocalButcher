import { MapPin, Package, ShoppingCart, User } from "lucide-react";
import Tooltip from "../Tooltip/Tooltip.jsx";

const NAV_ITEMS = [
  { key: "cart", label: "Cart", Icon: ShoppingCart },
  { key: "orders", label: "Orders", Icon: Package },
  { key: "addresses", label: "Addresses", Icon: MapPin },
  { key: "account", label: "Account", Icon: User },
];

/**
 * Slim, sticky glass header carrying the LocalButcher brand mark plus
 * icon entry points into the four slide-over panels.
 *
 * @param {() => void} [onLogoClick] - resets the conversation
 * @param {(panel: "cart"|"orders"|"addresses"|"account") => void} onOpenPanel
 */
function Header({ onLogoClick, onOpenPanel }) {
  return (
    <header className="glass sticky top-0 z-20 w-full border-b border-line shadow-sm">
      <div className="mx-auto flex max-w-content items-center justify-between px-6 py-4 sm:px-8">
        <button
          type="button"
          onClick={onLogoClick}
          className="group flex items-center gap-2.5 rounded-button transition focus-visible:outline-none"
        >
          <span className="text-2xl transition-transform duration-200 group-hover:animate-wobble">
            🥩
          </span>
          <span className="font-display text-xl font-bold tracking-tight text-ink">
            Local<span className="text-red">Butcher</span>
          </span>
        </button>

        <nav className="flex items-center gap-1" aria-label="Account panels">
          {NAV_ITEMS.map(({ key, label, Icon }) => (
            <Tooltip key={key} label={label} side="bottom">
              <button
                type="button"
                onClick={() => onOpenPanel(key)}
                aria-label={label}
                className="
                  flex h-10 w-10 items-center justify-center rounded-full
                  text-ink-soft transition duration-200
                  hover:bg-line/60 hover:text-red
                  focus-visible:outline-none
                "
              >
                <Icon size={18} strokeWidth={2} />
              </button>
            </Tooltip>
          ))}
        </nav>
      </div>
    </header>
  );
}

export default Header;
