/** Nesta design tokens, translated from docs/specs/sources/evidence-base-ux/hifi.css. */
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        blue: { DEFAULT: '#0000FF', hover: '#0000d6', tint: '#ececff', tint2: '#f5f5ff', edge: '#c7c7ff' },
        navy: { DEFAULT: '#0F294A', 70: '#576980', 40: '#9FA9B7', 20: '#CFD4DB' },
        ink: '#1c1c1e',
        grey: '#646363',
        line: { DEFAULT: '#e4e4e7', 2: '#d3d3d8' },
        ground: '#f4f4f5',
        paper: { DEFAULT: '#ffffff', 2: '#fafafa' },
        sand: { DEFAULT: '#D2C9C0', 20: '#F6F4F2' },
        aqua: '#97D9E3',
        violet: '#A59BEE',
        green: { DEFAULT: '#18A48C', tint: '#e7f5f2', edge: '#b7e0d8', text: '#0c6b5a' },
        yellow: { DEFAULT: '#FDB633', tint: '#fff6e3', edge: '#f3d99a', text: '#8a5a00' },
        orange: { DEFAULT: '#FF6E47', tint: '#FFE2DA', edge: '#FFC5B5', text: '#a03616' },
        red: '#EB003B',
      },
      fontFamily: {
        display: ['Zosia Display', 'Archivo', 'Averta', 'Inter', 'system-ui', 'sans-serif'],
        sans: ['Averta', 'Mulish', 'Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: { none: '0', DEFAULT: '0', full: '9999px' },
      boxShadow: {
        card: '0 1px 3px rgba(15,41,74,.05)',
        panel: '0 10px 30px rgba(15,41,74,.14)',
      },
    },
  },
  plugins: [],
}
