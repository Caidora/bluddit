import { reactRouter } from '@react-router/dev/vite';
import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [tailwindcss(), reactRouter()],
  resolve: { alias: { '@': fileURLToPath(new URL('./app', import.meta.url)) } },
  // Discover lazy route dependencies before the first browser opens the SPA.
  optimizeDeps: {
    entries: ['./app/**/*.tsx'],
    include: [
      '@tanstack/react-query',
      'radix-ui',
      'lucide-react',
      'class-variance-authority',
      'clsx',
      'tailwind-merge',
    ],
  },
  server: { proxy: { '/api': process.env.BROWSER_API_ORIGIN ?? 'http://127.0.0.1:8000' } },
});
