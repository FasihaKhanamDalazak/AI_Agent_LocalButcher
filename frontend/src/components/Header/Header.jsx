import { useState } from "react";
import { MapPin, Menu, Package, ShoppingCart, User } from "lucide-react";
import Tooltip from "../Tooltip/Tooltip.jsx";
import SlideOver from "../SlideOver/SlideOver.jsx";

const NAV_ITEMS = [
  { key: "cart", label: "Cart", Icon: ShoppingCart },
  { key: "orders", label: "Orders", Icon: Package },
  { key: "addresses", label: "Addresses", Icon: MapPin },
  { key: "account", label: "Account", Icon: User },
];

/**
 * Slim, sticky glass header carrying the LocalButcher brand mark plus
 * entry points into the four slide-over panels.
 *
 * On narrow viewports the icon row doesn't have room to breathe next to
 * the wordmark, so it's replaced with a single hamburger button that opens
 * a left-side nav drawer listing the same four destinations (reusing
 * SlideOver's side="left" variant) — desktop/tablet keeps the direct icon
 * row, no extra tap needed there.
 *
 * @param {() => void} [onLogoClick] - resets the conversation
 * @param {(panel: "cart"|"orders"|"addresses"|"account") => void} onOpenPanel
 */
function Header({ onLogoClick, onOpenPanel }) {
  const [isNavOpen, setIsNavOpen] = useState(false);

  const openPanel = (key) => {
    setIsNavOpen(false);
    onOpenPanel(key);
  };

  return (
    <header className="glass sticky top-0 z-20 w-full border-b border-line shadow-sm">
      <div className="mx-auto flex max-w-content items-center justify-between px-6 py-4 sm:px-8">
        <button
          type="button"
          onClick={onLogoClick}
          className="group order-2 flex items-center gap-2.5 rounded-button transition focus-visible:outline-none sm:order-1"
        >
          <span className="text-2xl transition-transform duration-200 group-hover:animate-wobble">
            🥩
          </span>
          <span className="font-display text-xl font-bold tracking-tight text-ink">
            Local<span className="text-red">Butcher</span>
          </span>
        </button>

        <nav className="hidden items-center gap-1 sm:order-2 sm:flex" aria-label="Account panels">
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

        <button
          type="button"
          onClick={() => setIsNavOpen(true)}
          aria-label="Open menu"
          className="
            order-1 flex h-10 w-10 items-center justify-center rounded-full
            text-ink-soft transition duration-200
            hover:bg-line/60 hover:text-red
            focus-visible:outline-none sm:hidden
          "
        >
          <Menu size={20} strokeWidth={2} />
        </button>
      </div>

      <SlideOver isOpen={isNavOpen} onClose={() => setIsNavOpen(false)} title="Menu" side="left">
        <nav className="flex flex-col gap-1" aria-label="Account panels">
          {NAV_ITEMS.map(({ key, label, Icon }) => (
            <button
              key={key}
              type="button"
              onClick={() => openPanel(key)}
              className="
                flex items-center gap-3 rounded-button px-3 py-3 text-left
                text-sm font-medium text-ink transition duration-200
                hover:bg-line/60 hover:text-red
                focus-visible:outline-none
              "
            >
              <Icon size={18} strokeWidth={2} />
              {label}
            </button>
          ))}
        </nav>
      </SlideOver>
    </header>
  );
}

export default Header;
