import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "Georgia", "serif"],
      },
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        cream: "#f5f0e8",
        espresso: "#1c1917",
        wood: {
          DEFAULT: "#7c5a3a",
          dark: "#5c4028",
        },
      },
    },
  },
  plugins: [],
};
export default config;
