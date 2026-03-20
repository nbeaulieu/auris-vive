import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  base: '/auris-vive/proto/',
  build: {
    outDir: 'dist',
  },
  server: {
    port: 5173,
  },
});
