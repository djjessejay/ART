#!/usr/bin/env python3
"""Erzeugt bereinigte Mint-Assets aus assets/original nach assets/clean.

Schritte pro Token (gesteuert ueber collection.json -> tokens[].prepare):
  crop       : Bildausschnitt [left, top, right, bottom] (z. B. Smartphone-UI entfernen)
  poster     : erstes Frame eines GIF als PNG-Poster (image) speichern
  copy       : unveraendert uebernehmen (Original bleibt Masterdatei)

Deterministisch: gleiche Eingabe -> gleiche Ausgabe (PNG ohne Zeitstempel-Chunks).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ORIG = ROOT / "assets" / "original"
CLEAN = ROOT / "assets" / "clean"


def save_png(im: Image.Image, dst: Path) -> None:
    im.save(dst, format="PNG", optimize=True)


def main() -> int:
    manifest = json.loads((ROOT / "collection.json").read_text(encoding="utf-8"))
    # Verzeichnis neu aufbauen: Werke, die auf hold/exclude wechseln, duerfen nicht
    # als Altbestand im Pinning-Verzeichnis liegen bleiben.
    shutil.rmtree(CLEAN, ignore_errors=True)
    CLEAN.mkdir(parents=True)
    banner = manifest["collection"]["banner_source"]
    with Image.open(ORIG / banner) as im:
        save_png(im.convert("RGB"), CLEAN / "banner.png")
    print(f"[ok] banner.png <- {banner}")
    for tok in manifest["tokens"]:
        if tok["status"] != "mint":
            continue
        src = ORIG / tok["source"]
        prep = tok.get("prepare", {"op": "copy"})
        op = prep["op"]
        if op == "copy":
            dst = CLEAN / tok["image"]
            shutil.copyfile(src, dst)
        elif op == "crop":
            with Image.open(src) as im:
                save_png(im.convert("RGB").crop(tuple(prep["box"])), CLEAN / tok["image"])
        elif op == "poster":
            with Image.open(src) as im:
                im.seek(0)
                save_png(im.convert("RGB"), CLEAN / tok["image"])
            shutil.copyfile(src, CLEAN / tok["animation"])
        else:
            print(f"unbekannte Operation {op} fuer Token {tok['id']}", file=sys.stderr)
            return 1
        print(f"[ok] #{tok['id']:>2} {tok['name']} -> {op}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
