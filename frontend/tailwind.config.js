/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#141816",
        mist: "#eef1ef",
        leaf: "#2f6b4f",
        clay: "#b4532a",
        paper: "#f5f6f4",
        card: "#ffffff",
      },
      fontFamily: {
        display: [
          "\"Pretendard Variable\"",
          "Pretendard",
          "ui-sans-serif",
          "sans-serif",
        ],
        body: [
          "\"Pretendard Variable\"",
          "Pretendard",
          "ui-sans-serif",
          "sans-serif",
        ],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(20, 24, 22, 0.04), 0 8px 24px rgba(20, 24, 22, 0.06)",
        lift: "0 2px 4px rgba(20, 24, 22, 0.04), 0 16px 40px rgba(20, 24, 22, 0.08)",
      },
      borderRadius: {
        card: "1rem",
        chip: "9999px",
      },
      transitionTimingFunction: {
        soft: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};
