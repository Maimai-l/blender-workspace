#!/usr/bin/env python3
"""upload.py <local file> <remote path> : copy a local file to the Blender PC (through the exec server)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcx
print('uploaded', sys.argv[1], '->', sys.argv[2], pcx.put(sys.argv[1], sys.argv[2]), 'bytes')
