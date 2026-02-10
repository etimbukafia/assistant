/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        linen: '#F9F6F2',
        'accent-auburn': '#7E2E2E',
        'accent-copper': '#D97745',
        'sage-green': '#8A9A5B',
        burgundy: '#800020',
        'text-obsidian': '#050505',
        'text-muted': '#6B7280', // Approximate gray-500
      },
      fontFamily: {
        serif: ['"Playfair Display"', 'serif'],
        sans: ['"Inter"', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
