import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Relative asset URLs, so the build works from a subdirectory of a host as
  // happily as from its root, and from a pages site. Not from file:// -- the
  // entry is an ES module and browsers block those from a null origin.
  base: './',
  server: {
    // The generated data lives in web/, one level up: the API and the UI read
    // the same files rather than each keeping a copy.
    fs: { allow: ['..'] },
  },
  build: {
    outDir: 'dist',
    // Everything is one page and one dataset; a vendor split would cost a
    // round trip and save nothing.
    chunkSizeWarningLimit: 1200,
  },
});
