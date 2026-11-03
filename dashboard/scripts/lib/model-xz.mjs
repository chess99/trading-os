import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const fields = ["schema", "artifact_kind", "compression", "file", "compressed_bytes", "compressed_sha256", "expanded_bytes", "expanded_sha256", "expanded_media_type"];
export function xzManifestEntry(manifest, period, ticker, filename = `${period}-output.json`) {
  const exactCapital = ["600887", "002714", "603939", "600183", "603288"].includes(ticker) && period === "2026-Q3" && filename === "2026-Q3-capital-20261103-output.json";
  if ((!exactCapital && filename !== `${period}-output.json`) || !/^(?:20\d{2})-(?:FY|Q1|H1|Q3)$/u.test(period) || !manifest || Array.isArray(manifest) || Object.keys(manifest).sort().join() !== [...fields].sort().join()
      || manifest.schema !== "trading_os_lossless_json_xz_v1"
      || manifest.artifact_kind !== "transport_manifest_not_model_result"
      || manifest.compression !== "xz" || manifest.expanded_media_type !== "application/json"
      || manifest.file !== `${filename}.xz`
      || !Number.isSafeInteger(manifest.compressed_bytes) || manifest.compressed_bytes < 1 || manifest.compressed_bytes > 100 * 1024 ** 2
      || !Number.isSafeInteger(manifest.expanded_bytes) || manifest.expanded_bytes < 1 || manifest.expanded_bytes > 512 * 1024 ** 2
      || !/^[a-f0-9]{64}$/u.test(manifest.compressed_sha256 ?? "")
      || !/^[a-f0-9]{64}$/u.test(manifest.expanded_sha256 ?? "")) throw new Error("Unsafe XZ transport manifest");
  return manifest;
}
export function verifyXzBytes(bytes, manifest, ticker) {
  const match = /^((?:20\d{2})-(?:FY|Q1|H1|Q3))-output\.json\.xz$/u.exec(manifest?.file ?? "");
  const exactCapital = ["600887", "002714", "603939", "600183", "603288"].includes(ticker) && manifest?.file === "2026-Q3-capital-20261103-output.json.xz";
  if (!match && !exactCapital) throw new Error("Unsafe XZ transport manifest");
  xzManifestEntry(manifest, exactCapital ? "2026-Q3" : match[1], ticker, manifest.file.slice(0, -3));
  // Execute only the trusted repository codec verifier, never a research model.
  // Python's stdlib supplies bounded-memory XZ; no optional package or shell.
  const verifier = fileURLToPath(new URL("../verify-model-xz.py", import.meta.url));
  const run = spawnSync("python3", ["-I", verifier, JSON.stringify(manifest)], {
    input: bytes, timeout: 120_000, maxBuffer: 64 * 1024,
  });
  if (run.error || run.status !== 0) throw new Error(`XZ integrity verification failed: ${run.error?.message ?? run.stderr?.toString().trim() ?? run.status}`);
}
