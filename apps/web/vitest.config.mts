import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

// Component tests run in jsdom. esbuild's automatic JSX runtime means the
// components - which, like the rest of the app, never import React - compile
// without a React-in-scope reference. The `@/` alias mirrors tsconfig so tests
// import exactly what the app does; setup wires in jest-dom's matchers.
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  esbuild: {
    jsx: "automatic",
    jsxImportSource: "react",
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./test/setup.ts"],
    include: ["test/**/*.test.{ts,tsx}"],
  },
});
