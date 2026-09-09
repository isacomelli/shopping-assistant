import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "system-ui",
          "Roboto",
          "sans-serif",
        ],
      },
      colors: {
        canvas: "#f7f7f5",
        surface: "#ffffff",
        ink: {
          900: "#141412",
          700: "#3a3a35",
          500: "#6b6b63",
          300: "#a8a89e",
        },
        brand: {
          50: "#eef6f1",
          100: "#d7ebe0",
          300: "#8fcaa9",
          500: "#2f7d54",
          600: "#256641",
          700: "#1c4f33",
        },
        alert: {
          50: "#fdf3ea",
          500: "#b5651d",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(20, 20, 18, 0.04), 0 1px 12px rgba(20, 20, 18, 0.05)",
      },
      borderRadius: {
        xl2: "1.1rem",
      },
    },
  },
  plugins: [],
};

export default config;
