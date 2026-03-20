import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiTarget = process.env.API_PROXY_TARGET || "http://127.0.0.1:9003";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8083,
    proxy: {
      "/health": apiTarget,
      "/status": apiTarget,
      "/onboarding": apiTarget,
      "/ui": apiTarget,
      "/providers": apiTarget
    }
  },
  preview: {
    port: 8083
  }
});
