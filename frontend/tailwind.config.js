/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#F5F6F2",
        surface: "#FFFFFF",
        ink: "#151A17",
        muted: "#5B665F",
        border: "#E3E6DE",
        accent: "#245A4C",
        accentSoft: "#DCEAE4",
        negative: "#B94A34",
        negativeSoft: "#F6E4DF",
      },
      fontFamily: {
        display: ["Sora", "sans-serif"],
        body: ["Inter", "sans-serif"],
      },
      borderRadius: {
        card: "14px",
      },
    },
  },
  plugins: [],
};
