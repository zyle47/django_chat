#!/usr/bin/env python3
"""
ZYLE47 encoder.

Algorithm:
  1. XOR every byte of input with repeating key b"ZYLE47"
  2. Base64-encode the result
  3. Wrap in ZYLE47 header/footer
  4. Base64-encode the whole thing again (looks like plain base64 to the untrained eye)
"""
import sys
import base64

KEY = b"ZYLE47"


def zyle_encode(data: bytes) -> str:
    xored = bytes(b ^ KEY[i % len(KEY)] for i, b in enumerate(data))
    b64 = base64.b64encode(xored).decode()
    lines = [b64[i:i+64] for i in range(0, len(b64), 64)]
    inner = "===ZYLE47===\n" + "\n".join(lines) + "\n===END ZYLE47==="
    outer = base64.b64encode(inner.encode()).decode()
    return "\n".join(outer[i:i+64] for i in range(0, len(outer), 64))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <input_file>")
        sys.exit(1)
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    print(zyle_encode(data))
