/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'risk-high': '#ef4444',
        'risk-medium': '#f59e0b',
        'risk-low': '#10b981',
      }
    },
  },
  plugins: [],
}

// Made with Bob
