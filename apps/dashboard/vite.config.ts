import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath, URL } from "node:url";

export default defineConfig(({ command, mode }) => {
  const repositoryRoot = fileURLToPath(new URL("../..", import.meta.url));
  const fileEnvironment = loadEnv(mode, repositoryRoot, "");
  const target = process.env.BOTKERNEL_API_TARGET || fileEnvironment.BOTKERNEL_API_TARGET;
  if (command === "serve" && mode !== "test" && !target) {
    throw new Error("Set BOTKERNEL_API_TARGET in the repository .env file before starting the dashboard.");
  }
  return {
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    proxy: {
      "/api": {
        target: target || "http://127.0.0.1:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  };
});
