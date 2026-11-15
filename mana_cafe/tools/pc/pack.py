"""Pack any file into lossless 8-bit greyscale PNG pieces so the cloud session can read it through the exec
server's image reader, which returns PNG/JPEG files of at most 2000 x 2000 px unchanged.

    python pack.py <file> <out_dir>

Each piece is <out_dir>/<n>.png, 2000 px wide and 250 rows high: the reader passes files up to about 510 kB unchanged and re-encodes bigger ones as JPEG. Its first row holds a 16-byte header
(magic, piece index, piece count, payload length); the payload follows from row 1. Standard library only.
Prints one line per piece: the path and its payload size."""
import os
import struct
import sys
import zlib

src, out_dir = sys.argv[1], sys.argv[2]
W = 2000
piece = W * 249
os.makedirs(out_dir, exist_ok=True)
data = open(src, 'rb').read()
n = max(1, (len(data) + piece - 1) // piece)


def png(path, w, h, raw_rows):
    def chunk(t, b):
        c = struct.pack('>I', len(b)) + t + b
        return c + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
    body = b''.join(b'\x00' + r for r in raw_rows)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0)))
        f.write(chunk(b'IDAT', zlib.compress(body, 6)))
        f.write(chunk(b'IEND', b''))


for i in range(n):
    part = data[i * piece:(i + 1) * piece]
    hdr = b'QTPK' + struct.pack('>III', i, n, len(part))
    rows = [hdr + b'\x00' * (W - len(hdr))]
    for k in range(0, len(part), W):
        r = part[k:k + W]
        rows.append(r + b'\x00' * (W - len(r)))
    p = os.path.join(out_dir, '%03d.png' % i)
    png(p, W, len(rows), rows)
    print(p, len(part))
