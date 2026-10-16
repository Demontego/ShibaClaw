import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/static/desktop/",
  build: {
    outDir: "../static/desktop",
    emptyOutDir: true,
  },
});
