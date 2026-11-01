import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// The dashboard reads the committed, reconciled Task 007 data directly from the repository
// (../collaboration/reports/007-pilot-data/per-run-reconciled.json), so the dev server must be allowed to serve one level up.
export default defineConfig({
  plugins: [react()],
  base: "./",
  // Vite copies public/ verbatim, regardless of Git ignore rules. Demo assets
  // must be explicitly imported from reviewed source; local replay exports stay local.
  publicDir: false,
  server: { fs: { allow: [".."] } },
  test: { environment: "node", include: ["src/**/*.test.{ts,tsx}"] },
});
