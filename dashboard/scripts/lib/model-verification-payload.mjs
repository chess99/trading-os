// Closed verification ZIP transport; never executes/extracts the opaque payload.
import { createHash } from 'node:crypto';
import { constants } from 'node:fs';
import { lstat, open, realpath } from 'node:fs/promises';
import { join, resolve } from 'node:path';
export const PART_BYTES = 6 * 1024 ** 2;
export const MAX_PARTS = 32;
const fields = ['schema', 'period', 'payload_bytes', 'payload_sha256', 'parts'];
const hashPattern = /^[a-f0-9]{64}$/u;
function exactFields(value, expected) {
  return value && !Array.isArray(value) && typeof value === 'object'
    && Object.keys(value).sort().join() === [...expected].sort().join();
}
export function verificationManifestEntry(value, period) {
  if (typeof period !== 'string' || !/^(?:20\d{2})-(?:FY|Q1|H1|Q3)$/u.test(period)
      || !exactFields(value, fields) || value.schema !== 'trading_os_verification_payload_v1'
      || value.period !== period || !Number.isSafeInteger(value.payload_bytes)
      || value.payload_bytes <= 0 || value.payload_bytes > PART_BYTES * MAX_PARTS
      || typeof value.payload_sha256 !== 'string'
      || !hashPattern.test(value.payload_sha256) || !Array.isArray(value.parts)) {
    throw new Error('Unsafe verification manifest');
  }
  const count = Math.ceil(value.payload_bytes / PART_BYTES);
  if (value.parts.length !== count || count < 1 || count > MAX_PARTS) throw new Error('Invalid verification part count');
  value.parts.forEach((entry, index) => {
    const name = `${period}-verification-part-${String(index).padStart(3, '0')}.bin`;
    const size = Math.min(PART_BYTES, value.payload_bytes - index * PART_BYTES);
    if (!exactFields(entry, ['file', 'bytes', 'sha256']) || entry.file !== name
        || !Number.isSafeInteger(entry.bytes) || entry.bytes !== size
        || typeof entry.sha256 !== 'string' || !hashPattern.test(entry.sha256)) {
      throw new Error('Invalid verification part order, name, size or hash');
    }
  });
  return value;
}
export function parseVerificationManifest(bytes, period) {
  if (bytes.length > 64 * 1024) throw new Error('Oversized verification manifest');
  const value = JSON.parse(bytes.toString('utf8'));
  if (!bytes.equals(Buffer.from(JSON.stringify(value) + '\n', 'ascii'))) throw new Error('Canonical verification manifest bytes required');
  return verificationManifestEntry(value, period);
}
export async function verifyVerificationPayload(directory, manifest, period) {
  verificationManifestEntry(manifest, period);
  const root = resolve(directory);
  if (await realpath(root) !== root) throw new Error('Verification directory is indirect');
  const whole = createHash('sha256');
  let total = 0;
  for (const entry of manifest.parts) {
    const path = join(root, entry.file);
    const named = await lstat(path);
    if (!named.isFile() || named.isSymbolicLink() || named.nlink !== 1
        || named.size !== entry.bytes || await realpath(path) !== path) throw new Error('Unsafe verification part');
    const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
    let bytes;
    try {
      const before = await handle.stat();
      if (before.dev !== named.dev || before.ino !== named.ino || before.size !== named.size || before.nlink !== 1) throw new Error('Verification identity changed');
      const buffer = Buffer.alloc(entry.bytes + 1);
      let offset = 0;
      while (offset < buffer.length) {
        const result = await handle.read(buffer, offset, buffer.length - offset, offset);
        if (!result.bytesRead) break;
        offset += result.bytesRead;
      }
      bytes = buffer.subarray(0, offset);
      const after = await handle.stat();
      const current = await lstat(path);
      if (after.size !== before.size || after.mtimeMs !== before.mtimeMs || after.ctimeMs !== before.ctimeMs
          || current.ino !== before.ino || current.dev !== before.dev || current.isSymbolicLink() || after.nlink !== 1) throw new Error('Verification part changed');
    } finally { await handle.close(); }
    if (bytes.length !== entry.bytes || createHash('sha256').update(bytes).digest('hex') !== entry.sha256) throw new Error('Verification part hash mismatch');
    whole.update(bytes); total += bytes.length;
  }
  if (total !== manifest.payload_bytes || whole.digest('hex') !== manifest.payload_sha256) throw new Error('Whole verification ZIP mismatch');
  return manifest;
}
