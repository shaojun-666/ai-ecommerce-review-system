import { defineConfig } from "vitest/config"
import vue from "@vitejs/plugin-vue"
import { fileURLToPath, URL } from "node:url"

export default defineConfig({
  plugins: [
    {
      name: "mock-css-stub",
      enforce: "pre",
      transform(code, id) {
        if (typeof id === "string" && id.endsWith(".css")) {
          return { code: "export default {}", map: null }
        }
      },
    },
    vue(),
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "happy-dom",
    include: ["src/**/*.spec.ts", "src/**/*.test.ts"],
    globals: true,
    server: {
      deps: {
        inline: ["element-plus"],
      },
    },
  },
})
