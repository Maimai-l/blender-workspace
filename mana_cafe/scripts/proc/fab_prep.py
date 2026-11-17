"""Megascans (Fab) library preparation: finds every asset under D:\\fab_downloads, writes render-sized copies of its
textures to <project>\\assets\\fab\\<key>\\ and a manifest (assets\\fab\\manifest.json) for the Blender importer.

    fab_prep.py [key ...]        (no arguments: all assets; existing files are kept)

The scans come with 8K maps; nothing in this picture is closer than 10 m to the camera (4 mm per pixel), so 4K / 2K
copies lose nothing and keep the scene inside the GPU's memory.
"""
import os, sys, json, glob, time
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
SRC = r'D:\fab_downloads\VaultCache\FabLibrary'
DST = r'D:\Blender\Projects\mana_cafe\assets\fab'

# folder -> (key, kind, sizes)   sizes: longest side of colour / normal / other maps
ASSETS = {
    'Dry_Grass-472c99c7': ('dry_grass', 'plant', (4096, 2048, 2048)),
    'Dwarf_Birch-7f125b9e': ('dwarf_birch', 'plant', (4096, 2048, 2048)),
    'Dwarf_Willow-a5a85500': ('dwarf_willow', 'plant', (4096, 2048, 2048)),
    'Lingonberry-a9f7d56d': ('lingonberry', 'plant', (4096, 2048, 2048)),
    'Tufted_Grass-0b787346': ('tufted_grass', 'plant', (4096, 2048, 2048)),
    'Tundra_Grass-3d87458a': ('tundra_grass', 'plant', (4096, 2048, 2048)),
    'Wild_Grass-50d9a417': ('wild_grass', 'plant', (4096, 2048, 2048)),
    'Yellow_Flower-297473a0': ('yellow_flower', 'plant', (4096, 2048, 2048)),
    'Granite_Cliff-9253e224': ('granite_cliff', '3d', (4096, 4096, 2048)),
    'Japanese_Stone_Wall-1267e536': ('jp_wall', '3d', (4096, 4096, 2048)),
    'Massive_Tundra_Rock_Formation-baed3859': ('rock_formation', '3d', (4096, 4096, 2048)),
    'Mossy_Stone_Wall-2c7de1fc': ('mossy_wall', '3d', (4096, 4096, 2048)),
    'Snowy_Ground-6034e934': ('snowy_ground', '3d', (4096, 4096, 2048)),
    'Tundra_Boulder-2a8bf42b': ('boulder_a', '3d', (4096, 4096, 2048)),
    'Tundra_Boulder-4a368dcd': ('boulder_b', '3d', (4096, 4096, 2048)),
    'Tundra_Rocky_Ground-1af105c7': ('rocky_ground_a', '3d', (8192, 8192, 4096)),
    'Tundra_Rocky_Ground-bec360a2': ('rocky_ground_b', '3d', (8192, 8192, 4096)),
    'Tundra_Stone-a88c3e4c': ('stone', '3d', (2048, 2048, 1024)),
    'Fresh_Snow-6b239c80': ('fresh_snow', 'surface', (4096, 4096, 4096)),
    'Furniture_Fabric-2ad48ece': ('furniture_fabric', 'surface', (2048, 2048, 2048)),
    'Grassy_Soil-9b88de26': ('grassy_soil', 'surface', (4096, 4096, 4096)),
    'Gravel_Ground-c19d425f': ('gravel', 'surface', (4096, 4096, 4096)),
    'Plain_Wool_Fabric-bb875143': ('wool', 'surface', (2048, 2048, 2048)),
    'Rusty_Metal-b165d2ff': ('rusty_metal', 'surface', (4096, 4096, 4096)),
    'Worn_Wooden_Planks-8adf7249': ('planks', 'surface', (4096, 4096, 4096)),
    'Wall_Rust_Leakage-5daeec0e': ('leak_a', 'decal', (4096, 2048, 2048)),
    'Wall_Rust_Leakage-611c3537': ('leak_b', 'decal', (4096, 2048, 2048)),
}
# map name in the manifest <- file suffixes (gltf packs: T_<id>_<res>_<X>.png ; texture sets: <Name>_<id>_<res>_<Map>.jpg)
SUFFIX = {
    'B-O': 'color_alpha', 'B': 'color', 'N': 'normal', 'ORM': 'orm', 'ORT': 'ort', 'T': 'transl', 'F': 'fuzz',
    'BaseColor': 'color', 'Normal': 'normal', 'Roughness': 'rough', 'Displacement': 'disp', 'AO': 'ao',
    'Opacity': 'opacity', 'Transmission': 'transl', 'Cavity': None, 'Bump': None, 'Gloss': None, 'Specular': None,
}


def resize(src, dst, size, mode):
    if os.path.exists(dst):
        return Image.open(dst).size
    im = Image.open(src)
    if im.mode in ('I;16', 'I', 'F'):
        a = np.asarray(im, np.float32)
        a = a / (65535.0 if a.max() > 255 else 255.0)
        im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    if mode == 'RGBA' and im.mode != 'RGBA':
        im = im.convert('RGBA')
    elif mode == 'RGB' and im.mode != 'RGB':
        im = im.convert('RGB')
    elif mode == 'L' and im.mode != 'L':
        im = im.convert('L')
    s = max(im.size)
    if s > size:
        k = size / s
        im = im.resize((max(1, round(im.size[0] * k)), max(1, round(im.size[1] * k))), Image.LANCZOS)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if dst.endswith('.jpg'):
        im.save(dst, quality=93, subsampling=0)
    else:
        im.save(dst, compress_level=3)
    return im.size


def normal_is_gl(normal_path, disp_path):
    """True if the green channel of the normal map follows OpenGL (Y+), judged against the height map."""
    n = np.asarray(Image.open(normal_path).convert('RGB').resize((1024, 1024), Image.BILINEAR), np.float32) / 255.0
    h = np.asarray(Image.open(disp_path).convert('L').resize((1024, 1024), Image.BILINEAR), np.float32) / 255.0
    dhr = np.gradient(h, axis=0)
    dhc = np.gradient(h, axis=1)
    cg = float(np.corrcoef((n[..., 1] - 0.5).ravel(), dhr.ravel())[0, 1])      # GL: + ; DirectX: -
    cr = float(np.corrcoef((n[..., 0] - 0.5).ravel(), dhc.ravel())[0, 1])      # always -
    return cg, cr


def main(keys=None):
    t0 = time.time()
    man = {}
    mf = os.path.join(DST, 'manifest.json')
    if os.path.exists(mf):
        man = json.load(open(mf, encoding='utf-8'))
    for folder, (key, kind, sizes) in ASSETS.items():
        if keys and key not in keys:
            continue
        p = os.path.join(SRC, folder)
        entry = {'key': key, 'kind': kind, 'folder': folder, 'maps': {}}
        gl = glob.glob(os.path.join(p, 'gltf', '*', '*', 'standard', '*.gltf')) or \
            glob.glob(os.path.join(p, 'gltf', '*', '*', '*.gltf'))
        entry['gltf'] = gl[0] if gl else None
        js = glob.glob(os.path.join(p, 'gltf', '*', '*', '*.json')) + glob.glob(os.path.join(p, 'texture-set', '*', '*.json'))
        for jf in js:
            try:
                j = json.load(open(jf, encoding='utf-8'))
            except Exception:
                continue
            for m in j.get('meta', []):
                if m.get('key') in ('scanArea', 'height', 'length', 'width', 'tileable'):
                    entry.setdefault('meta', {})[m['key']] = m.get('value')
            for k in ('displacementScale', 'displacementBias'):
                if k in j:
                    entry.setdefault('meta', {})[k] = j[k]
        # texture-set maps win over the glTF pack (they include displacement and are already 4K)
        files = glob.glob(os.path.join(p, 'gltf', '*', '*', 'Textures', '*.png')) + \
            glob.glob(os.path.join(p, 'texture-set', '*', '*.jpg'))
        for f in sorted(files, key=lambda x: 'texture-set' in x):
            suf = os.path.splitext(os.path.basename(f))[0].split('_')[-1]
            name = SUFFIX.get(suf)
            if name is None:
                continue
            if name == 'color' and 'color_alpha' in [SUFFIX.get(os.path.splitext(os.path.basename(x))[0].split('_')[-1]) for x in files] and kind in ('plant', 'decal'):
                continue                                           # plants and decals: the B-O map carries both
            size = sizes[0] if name in ('color', 'color_alpha') else (sizes[1] if name == 'normal' else sizes[2])
            mode = 'RGBA' if name == 'color_alpha' else ('L' if name in ('disp', 'rough', 'ao', 'transl', 'fuzz', 'opacity') else 'RGB')
            ext = '.png' if name in ('color_alpha', 'normal') else '.jpg'
            dst = os.path.join(DST, key, name + ext)
            if 'texture-set' in f and os.path.exists(dst) and entry['maps'].get(name, {}).get('src', '').find('texture-set') < 0:
                os.remove(dst)                                     # replace the glTF-pack copy by the texture-set map
            try:
                wh = resize(f, dst, size, mode)
            except Exception as e:
                print('FAILED', f, e)
                continue
            entry['maps'][name] = {'file': dst, 'size': wh, 'src': f}
        if 'normal' in entry['maps'] and 'disp' in entry['maps']:
            cg, cr = normal_is_gl(entry['maps']['normal']['file'], entry['maps']['disp']['file'])
            entry['normal_test'] = {'corr_green_dh_drow': round(cg, 3), 'corr_red_dh_dcol': round(cr, 3)}
        man[key] = entry
        print('%-16s %-8s maps %s %s  %.0fs' % (key, kind, {k: v['size'][0] for k, v in entry['maps'].items()},
                                               entry.get('normal_test', ''), time.time() - t0), flush=True)
        os.makedirs(DST, exist_ok=True)
        json.dump(man, open(mf, 'w', encoding='utf-8'), indent=1)
    print('manifest', mf, len(man), 'assets')


if __name__ == '__main__':
    main(sys.argv[1:] or None)
