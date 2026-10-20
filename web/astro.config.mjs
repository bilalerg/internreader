// @ts-check
import react from "@astrojs/react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "astro/config";

// Site tamamen statik derlenir (dist/). Abonelik formu /api'ye istek atar:
// geliştirirken Vite bu istekleri yerel FastAPI'ye (8000) yönlendirir, sunucuda Caddy yönlendirir.
export default defineConfig({
  site: process.env.INTERNREADER_SITE_ADRESI ?? "http://localhost:4321",
  integrations: [react()],
  vite: {
    plugins: [tailwindcss()],
    server: {
      proxy: { "/api": "http://127.0.0.1:8000" },
    },
  },
});
