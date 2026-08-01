/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        mute: "#6B7280",
        line: "#E5E7EB",
        mist: "#F1F5F9",
        paper: "#F8FAFC",
        card: "#FFFFFF",
        brand: "#22C55E",
        "brand-dark": "#16A34A",
        violet: "#6366F1",
        global: "#3B82F6",
        local: "#F97316",
        clay: "#DC2626",
        // Keep `leaf` as alias so older classnames still resolve during transition.
        leaf: "#22C55E",
      },
      fontFamily: {
        display: [
          '"Pretendard Variable"',
          "Pretendard",
          "ui-sans-serif",
          "sans-serif",
        ],
        body: [
          '"Pretendard Variable"',
          "Pretendard",
          "ui-sans-serif",
          "sans-serif",
        ],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(17, 24, 39, 0.04), 0 8px 24px rgba(17, 24, 39, 0.06)",
        lift: "0 4px 8px rgba(17, 24, 39, 0.04), 0 18px 40px rgba(17, 24, 39, 0.08)",
        glow: "0 8px 28px rgba(34, 197, 94, 0.28)",
      },
      borderRadius: {
        card: "1.25rem",
        chip: "9999px",
      },
      backgroundImage: {
        "brand-gradient":
          "linear-gradient(135deg, #22C55E 0%, #16A34A 55%, #0EA5E9 120%)",
        "accent-gradient":
          "linear-gradient(135deg, #6366F1 0%, #3B82F6 100%)",
        "hero-glow":
          "radial-gradient(ellipse 80% 50% at 20% -10%, rgba(34,197,94,0.16), transparent 55%), radial-gradient(ellipse 60% 40% at 100% 0%, rgba(99,102,241,0.1), transparent 50%)",
      },
      transitionTimingFunction: {
        soft: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};
