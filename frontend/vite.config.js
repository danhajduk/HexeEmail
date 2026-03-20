import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8083,
    proxy: {
      "/health": "http://127.0.0.1:8080",
      "/status": "http://127.0.0.1:8080",
      "/onboarding": "http://127.0.0.1:8080",
      "/ui": "http://127.0.0.1:8080"
    }
  },
  preview: {
    port: 8083
  }
});
