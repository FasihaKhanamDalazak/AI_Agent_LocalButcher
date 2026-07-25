/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Exact LocalButcher brand tokens
        red: {
          DEFAULT: "#C0392B",
          dark: "#9C2B20",
          light: "#E05A4A",
        },
        brown: {
          DEFAULT: "#5D3A1A",
          soft: "#7A4F28",
        },
        gold: "#CAA43A",

        background: "#F2F3F5",
        cream: "#FBF7F2",

        ink: {
          DEFAULT: "#20140C",
          soft: "#5B4A40",
        },

        line: "#E7E0D8",
        surface: "#FFFFFF",

        success: "#1F8F54",
        error: "#DC2626",
      },
      fontFamily: {
        display: ["Fraunces", "serif"],
        sans: ["Plus Jakarta Sans", "system-ui", "sans-serif"],
      },
      borderRadius: {
        card: "22px",
        "card-sm": "14px",
        button: "9999px",
        input: "18px",
        chip: "9999px",
      },
      boxShadow: {
        sm: "0 2px 8px rgba(46,24,12,.06)",
        card: "0 18px 50px -20px rgba(93,58,26,.35)",
        "card-lg": "0 40px 90px -30px rgba(93,58,26,.5)",
        glow: "0 14px 30px -10px rgba(192,57,43,.7)",
        "glow-lg": "0 22px 44px -12px rgba(192,57,43,.85)",
      },
      backgroundImage: {
        "red-gradient": "linear-gradient(135deg, #E05A4A, #C0392B 55%, #9C2B20)",
        "grad-text": "linear-gradient(115deg, #E05A4A, #C0392B 40%, #5D3A1A)",
        "brown-gradient": "linear-gradient(135deg, #5D3A1A, #3A2410 60%, #9C2B20)",
      },
      maxWidth: {
        content: "1180px",
        chat: "900px",
      },
      transitionTimingFunction: {
        premium: "cubic-bezier(.22, 1, .36, 1)",
      },
      keyframes: {
        shimmer: {
          to: { backgroundPosition: "220% center" },
        },
        shimmerFast: {
          "0%": { backgroundPosition: "200% center" },
          "100%": { backgroundPosition: "-200% center" },
        },
        sweep: {
          "0%": { transform: "translateX(-150%) skewX(-20deg)" },
          "100%": { transform: "translateX(250%) skewX(-20deg)" },
        },
        blink: {
          "0%, 49%": { opacity: 1 },
          "50%, 100%": { opacity: 0 },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-12px)" },
        },
        floaty: {
          from: { transform: "translateY(0) rotate(var(--r, 0deg))" },
          to: { transform: "translateY(-28px) rotate(calc(var(--r, 0deg) + 10deg))" },
        },
        drift1: {
          to: { transform: "translate(-8vw, 10vh) scale(1.15)" },
        },
        drift2: {
          to: { transform: "translate(10vw, -8vh) scale(1.2)" },
        },
        pulseDot: {
          "0%": { boxShadow: "0 0 0 0 rgba(192,57,43,.55)" },
          "70%": { boxShadow: "0 0 0 10px rgba(192,57,43,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(192,57,43,0)" },
        },
        sheen: {
          "0%": { left: "-130%" },
          "100%": { left: "150%" },
        },
        wobble: {
          "0%, 100%": { transform: "rotate(0)" },
          "30%": { transform: "rotate(-12deg) scale(1.1)" },
          "60%": { transform: "rotate(8deg) scale(1.08)" },
        },
      },
      animation: {
        shimmer: "shimmer 7s linear infinite",
        "shimmer-fast": "shimmerFast 1.4s ease-in-out infinite",
        sweep: "sweep 1.6s ease-in-out infinite",
        blink: "blink 1s step-start infinite",
        float: "float 5s cubic-bezier(.22,1,.36,1) infinite",
        "float-d1": "float 5s cubic-bezier(.22,1,.36,1) infinite -1.6s",
        "float-d2": "float 5s cubic-bezier(.22,1,.36,1) infinite -3.2s",
        floaty: "floaty 8s cubic-bezier(.22,1,.36,1) infinite alternate",
        drift1: "drift1 22s cubic-bezier(.22,1,.36,1) infinite alternate",
        drift2: "drift2 26s cubic-bezier(.22,1,.36,1) infinite alternate",
        "pulse-dot": "pulseDot 2s infinite",
        wobble: "wobble 0.6s cubic-bezier(.22,1,.36,1)",
      },
    },
  },
  plugins: [],
};
