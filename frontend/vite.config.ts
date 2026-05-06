import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:5757",
    },
  },
  build: {
    outDir: "../backend/static",
    emptyOutDir: true,
  },
});
