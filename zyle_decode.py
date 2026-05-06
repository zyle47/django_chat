#!/usr/bin/env python3
"""
ZYLE47 decoder.

Algorithm (reverse of zyle_encode):
  1. Base64-decode the outer layer
  2. Strip ZYLE47 header/footer
  3. Base64-decode the inner layer
  4. XOR every byte with repeating key b"ZYLE47"
"""
import sys
import base64

KEY = b"ZYLE47"


def zyle_decode(text: str) -> bytes:
    outer = base64.b64decode("".join(text.strip().splitlines())).decode()
    lines = outer.strip().splitlines()
    if lines[0] != "===ZYLE47===" or lines[-1] != "===END ZYLE47===":
        raise ValueError("not a valid ZYLE47 file")
    xored = base64.b64decode("".join(lines[1:-1]))
    return bytes(b ^ KEY[i % len(KEY)] for i, b in enumerate(xored))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <input_file>")
        sys.exit(1)
    with open(sys.argv[1], "r") as f:
        text = f.read()
    sys.stdout.buffer.write(zyle_decode(text))
