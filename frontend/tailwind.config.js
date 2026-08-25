/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#F5F3EC",
        surface: "#FFFFFF",
        surfaceAlt: "#FBFAF6",
        ink: "#161E1A",
        muted: "#63705F",
        border: "#E4E1D5",
        borderStrong: "#D2CDB9",
        accent: "#1F5C46",
        accentDeep: "#123A2C",
        accentSoft: "#DCEAE0",
        gold: "#B8823E",
        goldSoft: "#F1E3CC",
        negative: "#B3452F",
        negativeSoft: "#F5E1D9",
      },
      fontFamily: {
        display: ["Sora", "sans-serif"],
        body: ["Inter", "sans-serif"],
        mono: ["\"JetBrains Mono\"", "ui-monospace", "monospace"],
      },
      borderRadius: {
        card: "18px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(22, 30, 26, 0.04), 0 8px 24px -12px rgba(22, 30, 26, 0.10)",
        cardHover: "0 2px 4px rgba(22, 30, 26, 0.05), 0 16px 32px -12px rgba(22, 30, 26, 0.16)",
        pop: "0 12px 32px -8px rgba(31, 92, 70, 0.28)",
      },
      backgroundImage: {
        "grain": "radial-gradient(circle at 1px 1px, rgba(22,30,26,0.05) 1px, transparent 0)",
      },
    },
  },
  plugins: [],
};
