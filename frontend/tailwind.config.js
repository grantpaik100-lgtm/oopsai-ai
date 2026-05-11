/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        field: {
          50: "#f7f8f5",
          100: "#e8ece1",
          700: "#30412f",
          900: "#152116"
        }
      }
    },
  },
  plugins: [],
};
