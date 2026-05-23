/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#1A56A0', light: '#EBF2FA', dark: '#0C3D7A' },
      },
    },
  },
  plugins: [],
}
