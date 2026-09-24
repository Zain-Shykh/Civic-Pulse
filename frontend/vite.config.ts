import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// No API base URL configured here — the frontend never holds one.
// See docs/adr/0002-frontend-runtime-config.md: nginx proxies /api in
// every environment, so relative fetch("/api/...") calls just work.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: false,
  },
});
