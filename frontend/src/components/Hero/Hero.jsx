import { useReveal } from "../../hooks/useReveal.js";
import { Typewriter } from "react-simple-typewriter";

const FLOATIES = [
  { emoji: "🍗", x: "6%", y: "16%", size: "1.9rem", r: "-12deg", delay: "-1s" },
  { emoji: "🌿", x: "13%", y: "70%", size: "1.5rem", r: "10deg", delay: "-3s" },
  { emoji: "🥚", x: "3%", y: "42%", size: "1.6rem", r: "8deg", delay: "-2s" },
  { emoji: "🦐", x: "92%", y: "18%", size: "1.8rem", r: "12deg", delay: "-1.5s" },
  { emoji: "🌶️", x: "95%", y: "62%", size: "1.6rem", r: "-10deg", delay: "-3.5s" },
  { emoji: "🥩", x: "88%", y: "88%", size: "2rem", r: "6deg", delay: "-2.5s" },
];

/**
 * Landing hero. Reproduces localbutcher.com's headline treatment —
 * the exact fade-up reveal and shimmering gradient text — rebuilt for
 * Ria's chat landing rather than the marketing site.
 */
function Hero() {
  const titleIn = useReveal(60);
  const subIn = useReveal(120);

  return (
    <section className="relative overflow-hidden px-6 pb-8 pt-16 sm:px-8 sm:pt-24">
      {/* Ambient floating ingredient icons, ported from the marketing site */}
      <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden="true">
        {FLOATIES.map((f, i) => (
          <span
            key={i}
            className="absolute animate-floaty opacity-60 [filter:drop-shadow(0_6px_12px_rgba(93,58,26,.35))]"
            style={{
              left: f.x,
              top: f.y,
              fontSize: f.size,
              transform: `rotate(${f.r})`,
              animationDelay: f.delay,
              "--r": f.r,
            }}
          >
            {f.emoji}
          </span>
        ))}
      </div>

      <div className="mx-auto flex max-w-content flex-col items-center text-center">
        <h1
          className={`reveal ${titleIn ? "in" : ""} mt-5 font-display text-[clamp(2.4rem,6vw,4.2rem)] font-black leading-[1.03] tracking-tight text-ink`}
        >
          Welcome to
          <span className="grad-text"> LocalButcher</span>
        </h1>

        <p className={`reveal ${subIn ? "in" : ""} mt-5 max-w-xl text-lg text-ink-soft`}>
          <span className="block text-lg font-medium text-ink">I'm Your AI Assistant</span>

          <span className="mt-2 block font-medium text-lg text-ink">
            I can{" "}
            <span className="text-red">
              <Typewriter
                words={[
                  "Place An Order.",
                  "Track It In Real Time.",
                  "Recommend The Perfect Cut.",
                  "Manage Your Cart.",
                  "Talk To Me — I'm Listening.",
                ]}
                loop={0}
                cursor
                cursorStyle="|"
                typeSpeed={70}
                deleteSpeed={45}
                delaySpeed={1800}
              />
            </span>
          </span>
        </p>
      </div>
    </section>
  );
}

export default Hero;
