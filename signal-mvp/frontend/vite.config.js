import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
var stdin_default = defineConfig({
  plugins: [react()],
  server: { proxy: {
    "/api": "http://localhost:8000",
    "/health": "http://localhost:8000"
  } }
});
export {
  stdin_default as default
};
