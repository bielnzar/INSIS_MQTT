// tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html", // File HTML utama
    "./src/**/*.{vue,js,ts,jsx,tsx}", // Semua file Vue dan JS/TS di dalam src
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
