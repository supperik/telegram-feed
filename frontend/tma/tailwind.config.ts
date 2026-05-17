import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--tg-bg)',
        text: 'var(--tg-text)',
        hint: 'var(--tg-hint)',
        link: 'var(--tg-link)',
        button: 'var(--tg-button)',
        'button-text': 'var(--tg-button-text)',
        secondary: 'var(--tg-secondary-bg)',
      },
    },
  },
  plugins: [],
} satisfies Config;
