import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        arabic: ["Noto Naskh Arabic", "Cairo", "Arial", "sans-serif"],
        sans: ["Noto Naskh Arabic", "Cairo", "Arial", "sans-serif"],
      },
      colors: {
        naqla: {
          50:  "#f0f9ff",
          100: "#e0f2fe",
          500: "#0ea5e9",
          600: "#0284c7",
          700: "#0369a1",
          900: "#0c4a6e",
        },
      },
    },
  },
  plugins: [
    require("tailwindcss-rtl"),
  ],
};

export default config;
