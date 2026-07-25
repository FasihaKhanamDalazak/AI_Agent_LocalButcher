import { useEffect, useState } from "react";

/**
 * Reproduces localbutcher.com's exact hero reveal: elements start at
 * opacity 0 / translateY(34px) and animate in via requestAnimationFrame
 * right after mount, using the site's own cubic-bezier(.22,1,.36,1)
 * easing over 0.8s (see .reveal / .reveal.in in styles/index.css).
 *
 * @param {number} [delayMs=0] optional stagger delay before revealing
 * @returns {boolean} whether the "in" class should be applied
 */
export function useReveal(delayMs = 0) {
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    let rafId;
    const timerId = setTimeout(() => {
      rafId = requestAnimationFrame(() => setRevealed(true));
    }, delayMs);

    return () => {
      clearTimeout(timerId);
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [delayMs]);

  return revealed;
}
