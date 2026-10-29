# Complete model-output transport

The ordinary interface remains `PERIOD.py` plus its complete `PERIOD-output.json`.
A complete output that exceeds the repository host's single-file limit or the
authorized connector's request-body transport budget may use
one lossless XZ stream named exactly `PERIOD-output.json.xz`. No years, scenarios,
entities, or precision may be removed to fit transport limits.

In that case only, `PERIOD-output.json` is a **transport descriptor, not a model
result**. Its closed schema is:

```json
{
  "schema": "trading_os_lossless_json_xz_v1",
  "artifact_kind": "transport_manifest_not_model_result",
  "compression": "xz",
  "file": "2026-Q3-output.json.xz",
  "compressed_bytes": 1,
  "compressed_sha256": "replace with 64 lowercase hex characters",
  "expanded_bytes": 1,
  "expanded_sha256": "replace with 64 lowercase hex characters",
  "expanded_media_type": "application/json"
}
```

The numbers/digests above are placeholders, not a valid artifact. No model
values belong in this descriptor. Readers must download the XZ stream, check
its full size and SHA256, decompress it with Python's standard-library `lzma`,
and verify the full expanded size and SHA256 **before** parsing the expanded
JSON as the model result. The original single-file producer still emits or
writes the entire uncompressed result; its bytes must equal the expanded
artifact, not the descriptor. Independent recomputation consumes the actual
expanded result. Reports link and distinguish the producer, transport
descriptor, complete lossless XZ output, and independent checker.

The dashboard data build requires Python 3's standard library for this codec.
It executes only `dashboard/scripts/verify-model-xz.py`, never research code.
It accepts one complete XZ stream, rejects trailing/concatenated data and
truncation, bounds the decoder memory to 256 MiB, compressed size to 100 MiB,
expanded size to 512 MiB, and codec runtime to 120 seconds. A failed check
fails the build. These are transport safety limits, not financial assumptions.

Existing same-company/same-period download boundaries remain. Only the exact
XZ output name is allowed; arbitrary archives, URLs, traversal, symlinks and
orphan XZ files are not exported. Both compressed and expanded digests are
validated. This does not alter the existing complete-case manifest contract.
The reproduction test runs the producer in a fresh directory and compares its
**whole** generated output against the losslessly expanded bytes.

Connector delivery budgets are checked separately from codec safety limits.
Use ordinary JSON only when the entire encoded request fits with headroom;
for this delivery, outputs over 8 MiB use the same lossless XZ contract.
Budget UTF-8 and worst-case JSON escaping, and base64 expansion for binary
files, including envelope margin. Recompression may change the compressed
SHA but must preserve every expanded byte and its SHA. Never truncate model
outputs, substitute a summary, or interpret the descriptor as a result.
