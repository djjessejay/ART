#!/usr/bin/env python3
"""Baut ERC-721-Metadaten (OpenSea/Marketplace-Standard) und contractURI-JSON.

Eingaben:
  collection.json   Kuration, Texte, Traits
  analysis.json     technische Bildanalyse (tools/analyze.py)
  cids.json         optional: {"images": "<CID>", "collection": "<CID>"} nach dem Pinning

Ausgabe:
  build/metadata/<id>.json   Token-Metadaten
  build/collection.json      contractURI (Collection-Level)

--strict bricht ab, wenn noch Platzhalter (CID, Royalty-Empfaenger) vorhanden sind.
Das ist der Gate fuer Mainnet-Deployments.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
PLACEHOLDER = "REPLACE_WITH_IMAGES_CID"
ZERO = "0x0000000000000000000000000000000000000000"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="Platzhalter verbieten")
    args = ap.parse_args()

    manifest = json.loads((ROOT / "collection.json").read_text(encoding="utf-8"))
    analysis = {a["file"]: a for a in json.loads((ROOT / "analysis.json").read_text(encoding="utf-8"))}
    cids_path = ROOT / "cids.json"
    cids = json.loads(cids_path.read_text(encoding="utf-8")) if cids_path.exists() else {}
    img_cid = cids.get("images", PLACEHOLDER)
    col = manifest["collection"]

    errors: list[str] = []
    if args.strict and img_cid == PLACEHOLDER:
        errors.append("cids.json fehlt oder images-CID nicht gesetzt")
    if args.strict and col["fee_recipient"].lower() == ZERO:
        errors.append("collection.fee_recipient ist die Null-Adresse")

    clean = ROOT / "assets" / "clean"
    out_dir = BUILD / "metadata"
    # build/ komplett neu erzeugen, damit zurueckgezogene Tokens nicht mitgepinnt werden
    shutil.rmtree(BUILD, ignore_errors=True)
    out_dir.mkdir(parents=True)

    ids: list[int] = []
    for tok in manifest["tokens"]:
        if tok["status"] != "mint":
            continue
        tid = tok["id"]
        if tid in ids:
            errors.append(f"doppelte Token-ID {tid}")
        ids.append(tid)

        a = analysis[tok["source"]]
        img_file = clean / tok["image"]
        if not img_file.exists():
            errors.append(f"{img_file} fehlt, zuerst tools/prepare_assets.py ausfuehren")
            continue

        attrs = [{"trait_type": k, "value": v} for k, v in tok["attributes"].items()]
        attrs += [
            {"trait_type": "Edition", "value": "1/1"},
            {"trait_type": "Collection", "value": col["name"]},
            {"display_type": "number", "trait_type": "Neon Index", "value": round(a["neon_index"] * 100, 1), "max_value": 100},
            {"display_type": "number", "trait_type": "Saturation", "value": round(a["saturation"] * 100, 1), "max_value": 100},
            {"display_type": "number", "trait_type": "Luminance", "value": round(a["luminance"] * 100, 1), "max_value": 100},
            {"trait_type": "Dominant Color", "value": a["palette"][0]["hex"]},
            {"trait_type": "Creation", "value": "AI-assisted, artist-curated"},
        ]

        files = [{"uri": f"ipfs://{img_cid}/{tok['image']}", "type": "image/png", "sha256": sha256(img_file)}]
        meta = {
            "name": f"{tok['name']} #{tid}",
            "description": tok["description"],
            "image": f"ipfs://{img_cid}/{tok['image']}",
            "external_url": f"{col['external_link']}/nft/{tid}",
            "attributes": attrs,
            "properties": {
                "creator": col["creator"],
                "license": col["license"],
                "ai_disclosure": col["ai_disclosure"],
                "dimensions": f"{a['width']}x{a['height']}",
                "source_sha256": a["sha256"],
                "palette": [p["hex"] for p in a["palette"]],
                "files": files,
            },
        }
        if "animation" in tok:
            anim = clean / tok["animation"]
            meta["animation_url"] = f"ipfs://{img_cid}/{tok['animation']}"
            files.append({"uri": meta["animation_url"], "type": "image/gif", "sha256": sha256(anim)})

        (out_dir / f"{tid}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[ok] metadata/{tid}.json  {meta['name']}")

    if sorted(ids) != list(range(1, len(ids) + 1)):
        errors.append(f"Token-IDs muessen lueckenlos ab 1 laufen, gefunden {sorted(ids)}")

    contract_meta = {
        "name": col["name"],
        "description": col["description"],
        "image": f"ipfs://{img_cid}/banner.png",
        "banner_image": f"ipfs://{img_cid}/banner.png",
        "external_link": col["external_link"],
        "seller_fee_basis_points": col["seller_fee_basis_points"],
        "fee_recipient": col["fee_recipient"],
    }
    (BUILD / "collection.json").write_text(json.dumps(contract_meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[ok] collection.json  maxSupply={len(ids)}")

    if errors:
        for e in errors:
            print(f"[fehler] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
