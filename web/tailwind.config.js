/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Sunset Monochromatic Orange Palette
        sunset: {
          50: '#fff7ed',
          100: '#ffedd5',
          200: '#fed7aa',
          300: '#fdba74',
          400: '#fb923c',
          500: '#f97316',  // Primary
          600: '#ea580c',
          700: '#c2410c',
          800: '#9a3412',
          900: '#7c2d12',
          950: '#431407',
        },
        // Bravo Zero - Warm tinted dark palette
        bravo: {
          bg: '#0c0906',
          surface: '#1a1310',
          elevated: '#241c17',
          border: '#3d2f25',
          'border-subtle': '#2a211a',
          text: '#fef7f0',
          'text-secondary': '#d4c4b5',
          muted: '#9a8a7a',
          // Legacy aliases
          primary: '#1a1310',
          secondary: '#241c17',
          accent: '#f97316',
        },
      },
      fontFamily: {
        sans: ['DM Sans', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        'sunset': '0 0 20px -5px rgba(249, 115, 22, 0.25)',
        'sunset-lg': '0 0 40px -10px rgba(249, 115, 22, 0.35)',
        'glow': '0 0 60px rgba(249, 115, 22, 0.15)',
      },
      backgroundImage: {
        'gradient-sunset': 'linear-gradient(135deg, #f97316 0%, #c2410c 100%)',
        'gradient-sunset-light': 'linear-gradient(135deg, #fb923c 0%, #ea580c 100%)',
        'gradient-sunset-subtle': 'linear-gradient(135deg, #7c2d12 0%, #0c0906 100%)',
      },
    },
  },
  plugins: [],
};
