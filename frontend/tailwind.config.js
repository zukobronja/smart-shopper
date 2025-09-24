/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './src/**/*.{js,ts,jsx,tsx}',
    './index.html'
  ],
  theme: {
    extend: {
      colors: {
        teal: {
          300: '#5EEAD4',
          400: '#2DD4BF', 
          500: '#14B8A6',
          600: '#0D9488'
        },
        indigo: {
          300: '#A5B4FC',
          400: '#818CF8',
          500: '#6366F1',
          600: '#4F46E5'
        }
      },
      backdropBlur: {
        'xs': '2px',
        'sm': '4px',
        'md': '12px',
        'lg': '16px',
        'xl': '24px',
        '2xl': '40px',
        '3xl': '64px',
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.37)',
        'glass-lg': '0 25px 80px rgba(0, 0, 0, 0.35)',
        'glass-sm': '0 2px 30px rgba(0, 0, 0, 0.12)',
        'glass-md': '0 10px 40px rgba(0, 0, 0, 0.18)',
        'teal-glow': '0 6px 30px rgba(26, 182, 178, 0.25)',
      }
    },
  },
  plugins: [],
}
