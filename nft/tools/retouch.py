#!/usr/bin/env python3
"""Deterministische Retusche fuer Wave-II-Quellen -> assets/retouched/

Operationen (gesteuert ueber collection.json -> tokens[].retouch):
  pattern_patch : Rechteck mit Inhalt derselben Zeile ueberschreiben, horizontal um
                  ein Vielfaches der Rasterperiode verschoben. Fuer regelmaessige
                  Hintergruende (Noppenplatte). Die Verschiebung wird auf einem
                  sauberen Referenzstreifen automatisch feinjustiert.
  inpaint       : OpenCV-Telea-Inpainting einer Ellipsen-Maske. Fuer kleine Objekte
                  auf glatten Flaechen (Emblem auf Motorhaube).

Retuschierte Dateien sind neue Masterquellen und werden mit Hash in analysis.json
gefuehrt. Originale bleiben unveraendert zur Nachvollziehbarkeit.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ORIG = ROOT / "assets" / "original"
OUT = ROOT / "assets" / "retouched"


def pattern_patch(img: np.ndarray, box: list[int], shift_range: list[int], axis: str = "y") -> np.ndarray:
    """Ueberschreibt box mit dem um d Pixel versetzten Nachbarinhalt (oberhalb bzw. links).

    d wird so gewaehlt, dass der direkt angrenzende saubere Streifen gleicher Hoehe
    bzw. Breite am besten mit seinem eigenen Versatz uebereinstimmt (Rasterperiode).
    """
    x0, y0, x1, y1 = box
    h, w = y1 - y0, x1 - x0

    def region(dx: int, dy: int) -> np.ndarray:
        return img[y0 - dy : y1 - dy, x0 - dx : x1 - dx].astype(np.float32)

    best, best_err = shift_range[0], float("inf")
    for d in range(shift_range[0], shift_range[1] + 1):
        if axis == "y":
            ref, cand = region(0, h), region(0, h + d)
        else:
            ref, cand = region(w, 0), region(w + d, 0)
        err = float(np.mean((cand - ref) ** 2))
        if err < best_err:
            best, best_err = d, err
    out = img.copy()
    sx, sy = (0, best) if axis == "y" else (best, 0)
    patch = img[y0 - sy : y1 - sy, x0 - sx : x1 - sx].astype(np.float32)
    # Helligkeitsverlauf angleichen: Farbdifferenz an den vier Raendern (je 4 px ausserhalb
    # der Box) zwischen Ziel- und Quellposition, bilinear ueber die Box interpoliert.
    b = 4

    def edge_delta(sl_t, sl_s):
        return img[sl_t].astype(np.float32).mean((0, 1)) - img[sl_s].astype(np.float32).mean((0, 1))

    top = edge_delta(np.s_[y0 - b : y0, x0:x1], np.s_[y0 - sy - b : y0 - sy, x0 - sx : x1 - sx])
    bot = edge_delta(np.s_[y1 : y1 + b, x0:x1], np.s_[y1 - sy : y1 - sy + b, x0 - sx : x1 - sx])
    lft = edge_delta(np.s_[y0:y1, x0 - b : x0], np.s_[y0 - sy : y1 - sy, x0 - sx - b : x0 - sx])
    rgt = edge_delta(np.s_[y0:y1, x1 : x1 + b], np.s_[y0 - sy : y1 - sy, x1 - sx : x1 - sx + b])
    ty = np.linspace(0, 1, h)[:, None, None]
    tx = np.linspace(0, 1, w)[None, :, None]
    corr = 0.5 * ((1 - ty) * top + ty * bot) + 0.5 * ((1 - tx) * lft + tx * rgt)
    out[y0:y1, x0:x1] = np.clip(patch + corr, 0, 255).astype(np.uint8)
    print(f"      pattern_patch axis={axis} shift={best}px ref_mse={best_err:.1f} edge_corr={np.round((top + bot) / 2, 1).tolist()}")
    return out


def inpaint(img: np.ndarray, center: list[int], axes: list[int], radius: int) -> np.ndarray:
    mask = np.zeros(img.shape[:2], np.uint8)
    cv2.ellipse(mask, tuple(center), tuple(axes), 0, 0, 360, 255, -1)
    return cv2.inpaint(img, mask, radius, cv2.INPAINT_TELEA)


def main() -> int:
    manifest = json.loads((ROOT / "collection.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    for tok in manifest["tokens"]:
        ops = tok.get("retouch")
        if not ops:
            continue
        img = cv2.imread(str(ORIG / tok["original"]), cv2.IMREAD_COLOR)
        for op in ops:
            kind = op["op"]
            if kind == "pattern_patch":
                img = pattern_patch(img, op["box"], op["shift_range"], op.get("axis", "y"))
            elif kind == "inpaint":
                img = inpaint(img, op["center"], op["axes"], op.get("radius", 7))
            else:
                raise SystemExit(f"unbekannte Retusche {kind}")
        dst = ROOT / "assets" / "retouched" / Path(tok["source"]).name
        cv2.imwrite(str(dst), img, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        print(f"[ok] {tok['original']} -> retouched/{dst.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
