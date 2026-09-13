import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    // Le pool "forks" expire sous Windows quand le chemin contient des espaces.
    pool: "threads",
    // Un worker réutilisé pour tous les fichiers : ~18 s de démarrage économisés par fichier sur une
    // machine chargée (nos tests n'ont pas d'état global partagé ; cleanup() après chaque test).
    isolate: false,
    fileParallelism: false,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
});
