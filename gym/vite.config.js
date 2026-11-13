import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base './' para que funcione en cualquier subcarpeta (GitHub Pages: /<repo>/gym/)
export default defineConfig({
  base: './',
  plugins: [react()],
});
