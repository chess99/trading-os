import vinext from "vinext";
import { defineConfig } from "vite";

// macOS Seatbelt blocks FSEvents, so Codex previews need polling for HMR.
const isCodexSeatbeltSandbox = process.env.CODEX_SANDBOX === "seatbelt";

const workerConfig = {
  name: "trading-os-dashboard",
  main: "./worker/index.ts",
  compatibility_date: "2026-09-14",
  compatibility_flags: ["nodejs_compat"],
  observability: { enabled: true },
};

export default defineConfig(async ({ command }) => {
  // Keep Wrangler and Miniflare state project-local. These are non-secret tool
  // settings; application environment belongs in ignored `.env*` files.
  process.env.WRANGLER_WRITE_LOGS ??= "false";
  process.env.WRANGLER_LOG_PATH ??= ".wrangler/logs";
  process.env.MINIFLARE_REGISTRY_PATH ??= ".wrangler/registry";

  // Keep the deployment date pinned. The installed local workerd supports
  // 2026-05-22; this read-only app uses no newer runtime APIs during development.
  const { cloudflare } = await import("@cloudflare/vite-plugin");
  const activeWorkerConfig = command === "serve"
    ? { ...workerConfig, compatibility_date: "2026-05-22" }
    : workerConfig;

  return {
    server: {
      host: "127.0.0.1",
      watch: isCodexSeatbeltSandbox
        ? { useFsEvents: false, usePolling: true }
        : undefined,
    },
    plugins: [
      vinext(),
      cloudflare({
        viteEnvironment: { name: "rsc", childEnvironments: ["ssr"] },
        config: activeWorkerConfig,
      }),
    ],
  };
});
