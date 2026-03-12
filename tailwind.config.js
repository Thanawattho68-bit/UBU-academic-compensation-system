/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.js"
  ],
  theme: {
    extend: {
      colors: {
        ubu: {
          primary: '#1e293b',
          secondary: '#475569',
          accent: '#3b82f6',
          'accent-hover': '#2563eb',
          success: '#10b981',
          warning: '#f59e0b',
          danger: '#ef4444',
          neutral: '#94a3b8',
          info: '#3b82f6',
          bg: '#f8fafc',
          card: '#ffffff'
        }
      },
      fontFamily: {
        sans: ['Sarabun', 'sans-serif'],
      }
    },
  },
  plugins: [],
}

