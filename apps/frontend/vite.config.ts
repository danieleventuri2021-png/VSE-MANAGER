import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: Number(process.env.VITE_FRONTEND_PORT || 5173),
  },
  build: {
    sourcemap: false,
    target: "es2020",
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("/react-dom/") || id.includes("\\react-dom\\")) return "vendor-react";
          if (id.includes("/react/") || id.includes("\\react\\")) return "vendor-react";
          if (id.includes("axios")) return "vendor-axios";
          if (id.includes("lucide-react")) return "vendor-icons";
          return "vendor";
        },
      },
    },
  },
});
