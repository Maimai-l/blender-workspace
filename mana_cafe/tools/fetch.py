#!/usr/bin/env python3
"""fetch.py <remote_path> <local_path> : copy a file from the Blender PC to this session (any size or type).
Goes through the exec server: pack.py on the PC wraps the file into lossless PNG pieces (see pcx.py)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcx
n = pcx.fetch(sys.argv[1], sys.argv[2])
print('fetched', n, 'bytes ->', sys.argv[2])
