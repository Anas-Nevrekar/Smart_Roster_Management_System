/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17212f",
        muted: "#667085",
        line: "#e3e8ef",
        canvas: "#f6f8fb",
        brand: "#275dad",
      },
    },
  },
  plugins: [],
};
