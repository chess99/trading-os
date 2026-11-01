// Actual full-output transport, NOT verification evidence. Original single-XZ is unchanged.
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
export const OUTPUT_PART_BYTES = 6 * 1024 ** 2;
export const EIGHT_NAMES = ['production', 'literal', 'supplement-a-production', 'supplement-a-literal', 'supplement-b-production', 'supplement-b-literal', 'supplement-r-production', 'supplement-r-literal'];
const fields = (object, expected) => object && typeof object === 'object' && !Array.isArray(object) && Object.keys(object).sort().join() === [...expected].sort().join();
const hash = (value) => typeof value === 'string' && /^[a-f0-9]{64}$/u.test(value);
const positive = (value, cap) => Number.isSafeInteger(value) && value > 0 && value <= cap;
export function parseOutputParts(bytes, period, symbol, producerSha256) {
  if (!Buffer.isBuffer(bytes) || bytes.length > 64 * 1024 || !/^20\d{2}-(FY|Q1|H1|Q3)$/u.test(period) || !/^\d{6}$/u.test(symbol) || !hash(producerSha256)) throw new Error('Unsafe output context');
  const m = JSON.parse(bytes.toString('utf8'));
  // Duplicate keys, noncanonical numbers and alternate Unicode encodings cannot roundtrip.
  if (!bytes.equals(Buffer.from(JSON.stringify(m) + '\n', 'ascii'))) throw new Error('Canonical output manifest required');
  if (!fields(m, ['schema', 'artifact_kind', 'period', 'symbol', 'producer_sha256', 'layout', 'outputs']) || m.schema !== 'trading_os_lossless_json_xz_parts_v1' || m.artifact_kind !== 'transport_manifest_not_model_result' || m.period !== period || m.symbol !== symbol || m.producer_sha256 !== producerSha256) throw new Error('Unsafe output manifest identity');
  const names = m.layout === 'single_complete_json' && symbol !== '300015' ? ['main'] : m.layout === 'cn300015_complete_eight_json' && symbol === '300015' ? EIGHT_NAMES : null;
  if (!names || !Array.isArray(m.outputs) || m.outputs.length !== names.length) throw new Error('Incomplete output document coverage');
  let total = 0;
  m.outputs.forEach((entry, index) => {
    if (!fields(entry, ['name', 'compression', 'compressed_bytes', 'compressed_sha256', 'expanded_bytes', 'expanded_sha256', 'expanded_media_type', 'parts']) || entry.name !== names[index] || entry.compression !== 'xz' || entry.expanded_media_type !== 'application/json' || !positive(entry.compressed_bytes, 100 * 1024 ** 2) || !hash(entry.compressed_sha256) || !hash(entry.expanded_sha256)) throw new Error('Unsafe output document');
    let limit = 512 * 1024 ** 2;
    if (symbol === '600018' && entry.name === 'main' && producerSha256 === '53c9134dc98943c7222b845e6a503e4910e6c1552606fc2bc7a75d1a7d26d1f7' && entry.expanded_bytes === 670121548 && entry.expanded_sha256 === '308f5b98103a609927f18b27e06424545ab09d969f502082274cc9f6196a7959') limit = 670121548;
    if (!positive(entry.expanded_bytes, limit)) throw new Error('Unsafe expanded output size');
    total += entry.compressed_bytes;
    const count = Math.ceil(entry.compressed_bytes / OUTPUT_PART_BYTES);
    if (total > 192 * 1024 ** 2 || !Array.isArray(entry.parts) || entry.parts.length !== count || count > 32) throw new Error('Unsafe total output size or part count');
    entry.parts.forEach((part, partIndex) => {
      const name = `${period}-output-${entry.name}-part-${String(partIndex).padStart(3, '0')}.xzpart`;
      if (!fields(part, ['file', 'bytes', 'sha256']) || part.file !== name || part.bytes !== Math.min(OUTPUT_PART_BYTES, entry.compressed_bytes - partIndex * OUTPUT_PART_BYTES) || !hash(part.sha256)) throw new Error('Unsafe output part order, path, size or hash');
    });
  });
  return m;
}
export function verifyOutputParts(directory, bytes, period, symbol, producerSha256) {
  const manifest = parseOutputParts(bytes, period, symbol, producerSha256);
  const script = fileURLToPath(new URL('../verify-model-output-parts.py', import.meta.url));
  const result = spawnSync('python3', ['-I', '-B', script, directory, period, symbol, producerSha256], { input: bytes, timeout: 240_000, maxBuffer: 64 * 1024 });
  if (result.error || result.status !== 0) throw new Error(`Output parts integrity: ${result.error?.message ?? result.stderr?.toString().trim() ?? result.status}`);
  return manifest;
}
