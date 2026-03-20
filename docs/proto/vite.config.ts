import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  base: '/auris-vive/',
  publicDir: 'public',
  build: {
    outDir: 'dist',
  },
  server: {
    port: 5173,
  },
});
