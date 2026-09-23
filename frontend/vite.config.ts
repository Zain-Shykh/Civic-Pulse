import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// No API base URL configured here — the frontend never holds one.
// See docs/adr/0002-frontend-runtime-config.md: nginx proxies /api in
// every environment, so relative fetch("/api/...") calls just work.
export default defineConfig({
  plugins: [react()],
});
