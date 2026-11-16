#!/usr/bin/env python3
"""Pixel2Voxel (p2v): Bild -> Voxel-Relief als glTF-Binary (.glb)

Modell
------
Bild I (RGB) wird auf ein Raster W x H_g (Standard W=96, K=32, belegt in p2v/EXPERIMENTS.md) heruntergerechnet (Box-Filter, Seitenverhaeltnis
bleibt), auf eine Palette mit K Farben quantisiert (Median-Cut, deterministisch) und jede
Rasterzelle wird zu einer Voxelsaeule:

    h(x, y) = 1 + round( L(x, y)^gamma * (Z - 1) )       L = relative Luminanz Rec. 709

Leuchtende Pixel (Neon) stehen hoch, dunkle Flaechen bilden den Boden. Farbe = Palettenfarbe.

Geometrie
---------
Pro Saeule: Deckflaeche immer, Seitenflaechen nur dort, wo die Nachbarsaeule niedriger ist
(Hidden-Face-Culling), Boden entfaellt. Flache Normalen, Vertexfarben (COLOR_0, normiertes
UNSIGNED_BYTE), Material KHR_materials_unlit, damit Neonfarben unverfaelscht bleiben.

Ausgabe: GLB 2.0 (ein Buffer, ein Mesh, ein Node), plus Kennzahlen als dict.
Keine Abhaengigkeiten ausser Pillow und NumPy.
"""
from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from PIL import Image

# Einheitswuerfel-Kantenlaenge 1, Z = Hoehe. glTF ist Y-up: wir schreiben (x, z, y).


@dataclass
class P2VParams:
    width: int = 96          # Voxel in X (H7/H9 in p2v/EXPERIMENTS.md)
    colors: int = 32         # Palettengroesse K (H3 widerlegt fuer 16, H8 belegt fuer 32)
    max_height: int = 12     # Z
    gamma: float = 1.6       # >1 betont Leuchtpunkte, drueckt Mitteltoene


@dataclass
class P2VStats:
    grid_w: int
    grid_h: int
    voxels: int              # Summe aller Saeulenhoehen
    faces: int               # emittierte Quads nach Culling
    faces_naive: int         # Quads ohne Culling (6 pro Voxel)
    vertices: int
    glb_bytes: int
    palette: list[str]
    height_mean: float
    height_std: float
    delta_e_mean: float      # mittlere CIE76-Abweichung Raster vs. quantisiert


# ---------------------------------------------------------------- Farbe

def _srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    c = rgb.astype(np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def rasterize(img: Image.Image, p: P2VParams) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """-> (farbindex[H,W], palette[K,3], hoehe[H,W], delta_e_mean)"""
    rgb = img.convert("RGB")
    gw = p.width
    gh = max(1, round(rgb.height * gw / rgb.width))
    small = rgb.resize((gw, gh), Image.Resampling.BOX)
    q = small.quantize(colors=p.colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    idx = np.asarray(q, dtype=np.int32)
    pal = np.array(q.getpalette()[: 3 * p.colors], dtype=np.uint8).reshape(-1, 3)
    src = np.asarray(small, dtype=np.uint8)
    de = float(np.linalg.norm(_srgb_to_lab(src) - _srgb_to_lab(pal[idx]), axis=-1).mean())
    lum = (src.astype(np.float64) / 255.0) @ np.array([0.2126, 0.7152, 0.0722])
    height = 1 + np.rint(lum ** p.gamma * (p.max_height - 1)).astype(np.int32)
    return idx, pal, height, de


# ---------------------------------------------------------------- Geometrie

def build_mesh(idx: np.ndarray, pal: np.ndarray, height: np.ndarray):
    gh, gw = height.shape
    pos: list[tuple[float, float, float]] = []
    nrm: list[tuple[float, float, float]] = []
    col: list[tuple[int, int, int, int]] = []
    tri: list[int] = []
    ox, oy = gw / 2.0, gh / 2.0

    def quad(corners, normal, rgb):
        base = len(pos)
        for c in corners:
            # Bildzeile y waechst nach unten -> Welt-Z positiv nach vorne; glTF (x, up, z)
            pos.append((c[0] - ox, c[2], c[1] - oy))
            nrm.append(normal)
            col.append((int(rgb[0]), int(rgb[1]), int(rgb[2]), 255))
        tri.extend([base, base + 2, base + 1, base, base + 3, base + 2])

    def h_at(x, y):
        return int(height[y, x]) if 0 <= x < gw and 0 <= y < gh else 0

    faces = 0
    for y in range(gh):
        for x in range(gw):
            h = int(height[y, x])
            rgb = pal[idx[y, x]]
            # Deckflaeche (Normale +Y in glTF)
            quad([(x, y, h), (x + 1, y, h), (x + 1, y + 1, h), (x, y + 1, h)], (0.0, 1.0, 0.0), rgb)
            faces += 1
            # Seiten: nur sichtbarer Anteil oberhalb der Nachbarhoehe, leicht abgedunkelt
            side = (rgb.astype(np.int32) * 7 // 10).astype(np.uint8)
            for dx, dy, n, edge in (
                (1, 0, (1.0, 0.0, 0.0), ((x + 1, y), (x + 1, y + 1))),
                (-1, 0, (-1.0, 0.0, 0.0), ((x, y + 1), (x, y))),
                (0, 1, (0.0, 0.0, 1.0), ((x + 1, y + 1), (x, y + 1))),
                (0, -1, (0.0, 0.0, -1.0), ((x, y), (x + 1, y))),
            ):
                hn = h_at(x + dx, y + dy)
                if hn >= h:
                    continue
                (ax, ay), (bx, by) = edge
                quad([(ax, ay, hn), (bx, by, hn), (bx, by, h), (ax, ay, h)], n, side)
                faces += 1
    return (np.array(pos, np.float32), np.array(nrm, np.float32), np.array(col, np.uint8),
            np.array(tri, np.uint32), faces)


# ---------------------------------------------------------------- GLB

def _pad(b: bytes, fill: bytes = b"\x00") -> bytes:
    return b + fill * ((4 - len(b) % 4) % 4)


def write_glb(path: Path, pos, nrm, col, tri, name: str) -> int:
    use16 = len(pos) <= 65535
    idx_bytes = tri.astype(np.uint16 if use16 else np.uint32).tobytes()
    chunks = [_pad(pos.tobytes()), _pad(nrm.tobytes()), _pad(col.tobytes()), _pad(idx_bytes)]
    offsets = np.cumsum([0] + [len(c) for c in chunks[:-1]]).tolist()
    blob = b"".join(chunks)
    n = len(pos)
    gltf = {
        "asset": {"version": "2.0", "generator": "djjj-p2v 1.0"},
        "extensionsUsed": ["KHR_materials_unlit"],
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": name}],
        "materials": [{"name": "p2v-unlit", "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1],
                       "metallicFactor": 0, "roughnessFactor": 1}, "extensions": {"KHR_materials_unlit": {}}}],
        "meshes": [{"name": name, "primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "COLOR_0": 2},
                    "indices": 3, "material": 0, "mode": 4}]}],
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": offsets[0], "byteLength": pos.nbytes, "target": 34962},
            {"buffer": 0, "byteOffset": offsets[1], "byteLength": nrm.nbytes, "target": 34962},
            {"buffer": 0, "byteOffset": offsets[2], "byteLength": col.nbytes, "target": 34962},
            {"buffer": 0, "byteOffset": offsets[3], "byteLength": len(idx_bytes), "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": n, "type": "VEC3",
             "min": pos.min(0).tolist(), "max": pos.max(0).tolist()},
            {"bufferView": 1, "componentType": 5126, "count": n, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5121, "normalized": True, "count": n, "type": "VEC4"},
            {"bufferView": 3, "componentType": 5123 if use16 else 5125, "count": len(tri), "type": "SCALAR"},
        ],
    }
    js = _pad(json.dumps(gltf, separators=(",", ":")).encode(), b" ")
    total = 12 + 8 + len(js) + 8 + len(blob)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(js), b"JSON") + js)
        f.write(struct.pack("<I4s", len(blob), b"BIN\x00") + blob)
    return total


def load_frame(src: Path, crop: list[int] | None = None) -> Image.Image:
    """Erstes Frame (GIF) als RGB, optional zugeschnitten [left, top, right, bottom]."""
    with Image.open(src) as im:
        im.seek(0)
        frame = im.convert("RGB")
    return frame.crop(tuple(crop)) if crop else frame


def convert(src: Path, dst: Path, p: P2VParams, name: str | None = None, crop: list[int] | None = None) -> P2VStats:
    frame = load_frame(src, crop)
    idx, pal, height, de = rasterize(frame, p)
    pos, nrm, col, tri, faces = build_mesh(idx, pal, height)
    size = write_glb(dst, pos, nrm, col, tri, name or src.stem)
    return P2VStats(
        grid_w=height.shape[1], grid_h=height.shape[0], voxels=int(height.sum()), faces=faces,
        faces_naive=int(height.sum()) * 6, vertices=len(pos), glb_bytes=size,
        palette=["#{:02X}{:02X}{:02X}".format(*c) for c in pal],
        height_mean=round(float(height.mean()), 3), height_std=round(float(height.std()), 3),
        delta_e_mean=round(de, 3),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--width", type=int, default=96)
    ap.add_argument("--colors", type=int, default=32)
    ap.add_argument("--max-height", type=int, default=12)
    ap.add_argument("--gamma", type=float, default=1.6)
    a = ap.parse_args()
    s = convert(a.src, a.dst, P2VParams(a.width, a.colors, a.max_height, a.gamma))
    print(json.dumps(asdict(s), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
