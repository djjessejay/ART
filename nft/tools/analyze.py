#!/usr/bin/env python3
"""Technische Bildanalyse aller Originale -> analysis.json

Kennzahlen je Datei:
  sha256, format, width, height, aspect, frames, bytes
  palette      : 6 dominante Farben (Median-Cut) mit Anteil
  luminance    : mittlere relative Helligkeit (0..1, Rec. 709)
  saturation   : mittlere HSV-Saettigung (0..1)
  neon_index   : Anteil Pixel mit S>0.6 und V>0.6 (Leuchtfarben-Dichte)
  cyan_magenta : Verhaeltnis Cyan- zu Magenta-Pixeln (Synthwave-Balance)

Die Werte fliessen als numerische Traits in die NFT-Metadaten ein.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ORIG = ROOT / "assets" / "original"
RETOUCHED = ROOT / "assets" / "retouched"
SAMPLE = 256  # Analyse auf 256px Kantenlaenge, ausreichend fuer Farbstatistik


def _pixels(im: Image.Image):
    """Pillow >= 12.1: get_flattened_data, aeltere Versionen: getdata."""
    fn = getattr(im, "get_flattened_data", None)
    return fn() if fn else im.getdata()


def hexrgb(c: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*c)


def analyze(path: Path) -> dict:
    raw = path.read_bytes()
    with Image.open(path) as im:
        fmt, (w, h) = im.format, im.size
        frames = getattr(im, "n_frames", 1)
        im.seek(0)
        rgb = im.convert("RGB")
    small = rgb.copy()
    small.thumbnail((SAMPLE, SAMPLE))
    px = list(_pixels(small))
    n = len(px)

    q = small.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: 6 * 3]
    counts = sorted(q.getcolors(), reverse=True)
    palette = [
        {"hex": hexrgb(tuple(pal[i * 3 : i * 3 + 3])), "share": round(c / n, 4)}
        for c, i in counts
    ]

    hsv = list(_pixels(small.convert("HSV")))
    lum = sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in px) / (255 * n)
    sat = sum(s for _, s, _ in hsv) / (255 * n)
    neon = sum(1 for _, s, v in hsv if s > 153 and v > 153) / n
    # Farbtoene in PIL-HSV: 0..255 ~ 0..360 Grad. Cyan ~180-200 Grad, Magenta ~280-330 Grad
    cyan = sum(1 for hh, s, v in hsv if s > 120 and v > 120 and 120 <= hh <= 145)
    magenta = sum(1 for hh, s, v in hsv if s > 120 and v > 120 and 195 <= hh <= 235)

    return {
        "file": path.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "format": fmt,
        "width": w,
        "height": h,
        "aspect": f"{w / h:.3f}",
        "frames": frames,
        "palette": palette,
        "luminance": round(lum, 4),
        "saturation": round(sat, 4),
        "neon_index": round(neon, 4),
        "cyan_magenta": round(cyan / magenta, 3) if magenta else None,
    }


def main() -> int:
    dirs = [d for d in (ORIG, RETOUCHED) if d.is_dir()]
    out = [analyze(p) for d in dirs for p in sorted(d.iterdir()) if p.is_file()]
    (ROOT / "analysis.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    for a in out:
        print(
            f"{a['file']:<32} {a['width']}x{a['height']:<5} f={a['frames']:<3} "
            f"L={a['luminance']:.2f} S={a['saturation']:.2f} neon={a['neon_index']:.2f} "
            f"c/m={a['cyan_magenta']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
