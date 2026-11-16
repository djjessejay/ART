#!/usr/bin/env python3
"""Baut die P2V-Kollektion: Voxelmodelle (.glb), Vorschauen (.png), ERC-721-Metadaten.

  build/p2v/assets/<id>.glb     3D-Modell (animation_url)
  build/p2v/assets/<id>.png     Vorschau (image), gerendert mit three.js
  build/p2v/assets/banner.png   Collection-Banner
  build/p2v/metadata/<id>.json  Token-Metadaten
  build/p2v/collection.json     contractURI

Ablauf in zwei Stufen wie bei Genesis: Assets bauen -> pinnen (ASSETS_CID) -> Metadaten.
Die CID liest der Builder aus p2v/cids.json, sonst Platzhalter.

Gates:
  - Token auf "mint" mit offener Freigabe -> Abbruch
  - --strict: Platzhalter-CID, Null-Adresse, fehlende Vorschau -> Abbruch
  - --render: Vorschauen per tools/js/render_glb.js (braucht three + playwright)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from p2v import P2VParams, convert  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
COL = ROOT / "p2v"
OUT = ROOT / "build" / "p2v"
PLACEHOLDER = "REPLACE_WITH_ASSETS_CID"
ZERO = "0x0000000000000000000000000000000000000000"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--render", action="store_true", help="Vorschauen mit three.js rendern")
    a = ap.parse_args()

    m = json.loads((COL / "collection.json").read_text(encoding="utf-8"))
    col = m["collection"]
    params = P2VParams(**col["p2v_defaults"])
    cids_path = COL / "cids.json"
    cid = json.loads(cids_path.read_text())["assets"] if cids_path.exists() else PLACEHOLDER

    errors: list[str] = []
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "assets").mkdir(parents=True)
    (OUT / "metadata").mkdir(parents=True)
    shutil.copyfile(ROOT / "assets" / "original" / "10-twodivision-banner.png", OUT / "assets" / "banner.png")

    minted, reserved, stats = [], [], {}
    for t in m["tokens"]:
        if t["status"] == "hold":
            reserved.append(t["id"])
            continue
        if t["status"] != "mint":
            continue
        open_items = [c["item"] for c in t.get("clearance", []) if c["state"] != "done"]
        if open_items:
            errors.append(f"Token {t['id']} ({t['name']}) hat offene Freigaben: {open_items}")
            continue
        minted.append(t["id"])
        glb = OUT / "assets" / f"{t['id']}.glb"
        stats[t["id"]] = convert(ROOT / t["source"], glb, params, name=t["name"], crop=t.get("crop"))
        print(f"[ok] {t['id']}.glb  {stats[t['id']].glb_bytes / 1e6:.2f} MB  {t['name']}")

    all_ids = sorted(minted + reserved)
    if all_ids != list(range(1, len(all_ids) + 1)):
        errors.append(f"Token-IDs (mint + hold) muessen lueckenlos ab 1 laufen: {all_ids}")

    if a.render and minted:
        here = Path(__file__).parent / "js" / "render_glb.js"
        r = subprocess.run(["node", str(here), str(OUT / "assets"), *[str(OUT / "assets" / f"{i}.glb") for i in minted]],
                           env=os.environ.copy(), capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode:
            errors.append(f"Rendering fehlgeschlagen: {r.stderr.strip()[:400]}")

    for t in m["tokens"]:
        if t["id"] not in minted:
            continue
        s = stats[t["id"]]
        glb, png = OUT / "assets" / f"{t['id']}.glb", OUT / "assets" / f"{t['id']}.png"
        if a.strict and not png.exists():
            errors.append(f"Vorschau {png.name} fehlt (mit --render bauen)")
        attrs = [{"trait_type": k, "value": v} for k, v in t["attributes"].items()]
        attrs += [
            {"trait_type": "Edition", "value": "1/1"},
            {"trait_type": "Collection", "value": col["name"]},
            {"trait_type": "Format", "value": "glTF 2.0 Voxel Relief"},
            {"display_type": "number", "trait_type": "Grid Width", "value": s.grid_w},
            {"display_type": "number", "trait_type": "Grid Depth", "value": s.grid_h},
            {"display_type": "number", "trait_type": "Voxels", "value": s.voxels},
            {"display_type": "number", "trait_type": "Palette Colors", "value": len(s.palette)},
            {"display_type": "number", "trait_type": "Relief Variance", "value": s.height_std},
            {"trait_type": "Creation", "value": "AI-assisted source, deterministic p2v"},
        ]
        meta = {
            "name": f"{t['name']} #{t['id']}",
            "description": t["description"],
            "image": f"ipfs://{cid}/{t['id']}.png",
            "animation_url": f"ipfs://{cid}/{t['id']}.glb",
            "external_url": f"{col['external_link']}/p2v/{t['id']}",
            "attributes": attrs,
            "properties": {
                "creator": col["creator"], "license": col["license"], "ai_disclosure": col["ai_disclosure"],
                "p2v": {**asdict(params), "faces": s.faces, "vertices": s.vertices, "delta_e_mean": s.delta_e_mean},
                "source_sha256": sha256(ROOT / t["source"]),
                "files": [{"uri": f"ipfs://{cid}/{t['id']}.glb", "type": "model/gltf-binary", "sha256": sha256(glb)}]
                + ([{"uri": f"ipfs://{cid}/{t['id']}.png", "type": "image/png", "sha256": sha256(png)}] if png.exists() else []),
            },
        }
        (OUT / "metadata" / f"{t['id']}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    (OUT / "collection.json").write_text(json.dumps({
        "name": col["name"], "description": col["description"],
        "image": f"ipfs://{cid}/banner.png", "banner_image": f"ipfs://{cid}/banner.png",
        "external_link": col["external_link"], "seller_fee_basis_points": col["seller_fee_basis_points"],
        "fee_recipient": col["fee_recipient"]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[ok] p2v collection.json  mint={minted} reserviert(hold)={reserved} MAX_SUPPLY={len(all_ids)}")

    if a.strict and cid == PLACEHOLDER:
        errors.append("p2v/cids.json fehlt oder assets-CID nicht gesetzt")
    if a.strict and col["fee_recipient"].lower() == ZERO:
        errors.append("collection.fee_recipient ist die Null-Adresse")
    for e in errors:
        print(f"[fehler] {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
