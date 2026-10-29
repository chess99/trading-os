"""Verify one bounded XZ stream against a lossless-output transport descriptor.

Only reads stdin and reports integrity; never executes a producer or writes files.
The descriptor is metadata, not a model result. Consumers use the expanded JSON.
"""

import hashlib
import json
import lzma
import sys


def verify(stream, manifest):
    compressed = hashlib.sha256()
    expanded = hashlib.sha256()
    encoded_size = decoded_size = 0
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=256 * 1024**2)
    while chunk := stream.read(64 * 1024):
        encoded_size += len(chunk)
        if encoded_size > manifest["compressed_bytes"] or decoder.eof:
            raise ValueError("oversized or trailing XZ data")
        compressed.update(chunk)
        data = chunk
        while True:
            part = decoder.decompress(
                data, max_length=min(1024 * 1024, manifest["expanded_bytes"] - decoded_size + 1)
            )
            decoded_size += len(part)
            if decoded_size > manifest["expanded_bytes"]:
                raise ValueError("expanded bytes exceed declared bound")
            expanded.update(part)
            if decoder.eof:
                if decoder.unused_data:
                    raise ValueError("trailing or concatenated XZ data")
                break
            if decoder.needs_input:
                break
            data = b""
    if not decoder.eof:
        raise ValueError("truncated XZ stream")
    if (
        encoded_size != manifest["compressed_bytes"]
        or compressed.hexdigest() != manifest["compressed_sha256"]
        or decoded_size != manifest["expanded_bytes"]
        or expanded.hexdigest() != manifest["expanded_sha256"]
    ):
        raise ValueError("compressed or expanded size/hash mismatch")


if __name__ == "__main__":
    try:
        verify(sys.stdin.buffer, json.loads(sys.argv[1]))
    except (ValueError, KeyError, lzma.LZMAError) as error:
        raise SystemExit(str(error)) from error
