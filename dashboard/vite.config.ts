import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// The dashboard reads the committed, reconciled Task 007 data directly from the repository
// (../collaboration/reports/007-pilot-data/per-run-reconciled.json), so the dev server must be allowed to serve one level up.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: { fs: { allow: [".."] } },
  test: { environment: "node", include: ["src/**/*.test.{ts,tsx}"] },
});
