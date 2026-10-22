/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Requested High-Contrast Forest Green & Warm Off-White System
        background: '#F7F7F2',
        surface: '#FFFFFF',
        forest: {
          DEFAULT: '#123D2C',   // Primary dark green
          deep: '#0B2E22',      // Deep forest green
          dark: '#0B2E22',      // Deep forest green alias
          secondary: '#285B43', // Secondary green
          subtle: '#285B43',
          sage: '#E6EDE5',      // Pale sage
          light: '#E6EDE5',     // Pale sage alias
          border: '#CAD4C8',
        },
        sage: {
          DEFAULT: '#E6EDE5',
          light: '#F0F5EF',
          dark: '#CAD4C8',
        },
        ink: {
          DEFAULT: '#17251D',   // Main text
          secondary: '#6C776E', // Secondary text
          muted: '#6C776E',     // Secondary text alias
          faint: '#9BA59D',
        },
        border: {
          DEFAULT: '#E0E5DD',   // Borders
          subtle: '#EAEFE8',
          strong: '#CAD4C8',
        },
        // Compatibility Aliases for components using paper / terracotta
        paper: {
          DEFAULT: '#F7F7F2',
          warm: '#EFEFEA',
          card: '#FFFFFF',
          subtle: '#E6EDE5',
          border: '#E0E5DD',
          'border-strong': '#CAD4C8',
        },
        terracotta: {
          DEFAULT: '#B44A28',
          dark: '#8C3519',
          light: '#FAF0ED',
          border: '#F2C6B8',
        },
      },
      fontFamily: {
        serif: ['Newsreader', 'Lora', 'Georgia', 'serif'],
        sans: ['Plus Jakarta Sans', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'IBM Plex Mono', 'monospace'],
      },
      boxShadow: {
        'editorial-sm': '0 1px 2px rgba(18, 61, 44, 0.04)',
        'editorial': '0 2px 6px -1px rgba(18, 61, 44, 0.06), 0 1px 3px rgba(18, 61, 44, 0.03)',
        'editorial-lg': '0 12px 28px -6px rgba(18, 61, 44, 0.08), 0 4px 10px -2px rgba(18, 61, 44, 0.03)',
        'composer': '0 4px 20px -2px rgba(18, 61, 44, 0.05), 0 0 0 1px #E0E5DD',
        'composer-focus': '0 6px 24px -2px rgba(18, 61, 44, 0.10), 0 0 0 2px #123D2C',
        'sheet': '0 4px 20px -2px rgba(18, 61, 44, 0.05), 0 0 0 1px #E0E5DD',
      },
      borderRadius: {
        DEFAULT: '0.375rem',
        sm: '0.25rem',
        md: '0.375rem',
        lg: '0.5rem',
        xl: '0.75rem',
        '2xl': '1rem',
      },
    },
  },
  plugins: [],
}
