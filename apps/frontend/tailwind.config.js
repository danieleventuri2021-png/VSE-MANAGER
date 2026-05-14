/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#18212f",
        panel: "#f7f9fb",
        line: "#d7dde5",
        action: "#0f766e"
      }
    },
  },
  plugins: [],
};
