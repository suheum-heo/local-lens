/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#1a1f1c",
        mist: "#e8eee9",
        leaf: "#2f6b4f",
        clay: "#c45c26",
        paper: "#f7f5f0",
      },
      fontFamily: {
        display: ["\"Pretendard Variable\"", "Pretendard", "system-ui", "sans-serif"],
        body: ["\"Pretendard Variable\"", "Pretendard", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
