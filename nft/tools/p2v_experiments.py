#!/usr/bin/env python3
"""Hypothesentests fuer Pixel2Voxel -> p2v/experiments.json + p2v/EXPERIMENTS.md

Jede Hypothese hat ein vorab festgelegtes, messbares Kriterium. Ergebnis: belegt / widerlegt.
Die Kriterien stehen hier im Code, nicht im Nachhinein im Text.

H1 Culling      : Hidden-Face-Culling spart bei W=64 fuer jede Quelle >= 80 % der Flaechen.
H2 Dateigroesse : Bei W=64 bleibt jede GLB < 2 MB; bei W=128 ueberschreitet mind. eine 2 MB.
H3 Farbtreue    : K=16 haelt das mittlere Delta-E76 (Raster vs. quantisiert) fuer jede Quelle < 10.
H4 Relief       : Hoehenstreuung korreliert mit dem Neon-Index der Quelle, Pearson r > 0.5.
H5 Formerhalt   : SSIM(Draufsicht W=64, Quelle) >= 0.5 fuer jede Quelle (Vergleich auf 256 px).
H6 Determinismus: Zwei Laeufe mit gleichen Parametern erzeugen byte-identische GLB.

Phase 2 (konfirmatorisch). Aus Phase 1 abgeleitete Konfiguration W=96, K=32. Die Wahl beruht
auf den Phase-1-Daten und gilt dort nur explorativ. Getestet wird sie an einem Holdout-Set
(p2v/holdout), das nicht in die Parameterwahl eingeflossen ist:

H7 Formerhalt   : SSIM(Draufsicht W=96 K=32, Quelle) >= 0.5 fuer jedes Holdout-Bild.
H8 Farbtreue    : Delta-E76 bei K=32 < 10 fuer jedes Holdout-Bild.
H9 Dateigroesse : GLB bei W=96 K=32 < 2 MB fuer jedes Holdout-Bild.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from p2v import P2VParams, convert, load_frame, rasterize  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MB2 = 2 * 1024 * 1024


def neon_index(img: Image.Image) -> float:
    s = img.copy()
    s.thumbnail((256, 256))
    hsv = np.asarray(s.convert("HSV"), dtype=np.int32)
    return float(((hsv[..., 1] > 153) & (hsv[..., 2] > 153)).mean())


def ssim(a: np.ndarray, b: np.ndarray, win: int = 7) -> float:
    """SSIM (Wang et al. 2004) mit gleitendem Mittelwertfenster, Graustufen 0..255."""
    a, b = a.astype(np.float64), b.astype(np.float64)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2

    def box(x):
        k = np.ones(win) / win
        x = np.apply_along_axis(lambda r: np.convolve(r, k, mode="valid"), 1, x)
        return np.apply_along_axis(lambda c: np.convolve(c, k, mode="valid"), 0, x)

    ma, mb = box(a), box(b)
    va, vb, cov = box(a * a) - ma**2, box(b * b) - mb**2, box(a * b) - ma * mb
    s = ((2 * ma * mb + c1) * (2 * cov + c2)) / ((ma**2 + mb**2 + c1) * (va + vb + c2))
    return float(s.mean())


def topdown_ssim(img: Image.Image, p: P2VParams) -> float:
    idx, pal, _, _ = rasterize(img, p)
    top = Image.fromarray(pal[idx].astype(np.uint8))
    w = 256
    h = max(8, round(img.height * w / img.width))
    ref = np.asarray(img.resize((w, h), Image.Resampling.BOX).convert("L"))
    got = np.asarray(top.resize((w, h), Image.Resampling.NEAREST).convert("L"))
    return ssim(ref, got)


def main() -> int:
    manifest = json.loads((ROOT / "p2v" / "collection.json").read_text(encoding="utf-8"))
    sources = [(t["name"], ROOT / t["source"], t.get("crop")) for t in manifest["tokens"]]
    rows = []
    tmp = Path(tempfile.mkdtemp())
    for name, src, crop in sources:
        img = load_frame(src, crop)
        row = {"name": name, "source": src.name, "neon_index": round(neon_index(img), 4)}
        for w in (32, 64, 96, 128):
            st = convert(src, tmp / f"w{w}.glb", P2VParams(width=w, colors=16), crop=crop)
            row[f"w{w}"] = {"glb_bytes": st.glb_bytes, "faces": st.faces, "faces_naive": st.faces_naive,
                            "height_std": st.height_std, "delta_e": st.delta_e_mean}
        for k in (8, 16, 32):
            row[f"k{k}_delta_e"] = convert(src, tmp / "k.glb", P2VParams(width=64, colors=k), crop=crop).delta_e_mean
        row["ssim_w64"] = round(topdown_ssim(img, P2VParams(width=64, colors=16)), 4)
        row["ssim_w32"] = round(topdown_ssim(img, P2VParams(width=32, colors=16)), 4)
        h1 = hashlib.sha256((convert(src, tmp / "a.glb", P2VParams(width=64, colors=16), crop=crop), (tmp / "a.glb").read_bytes())[1]).hexdigest()
        h2 = hashlib.sha256((convert(src, tmp / "b.glb", P2VParams(width=64, colors=16), crop=crop), (tmp / "b.glb").read_bytes())[1]).hexdigest()
        row["deterministic"] = h1 == h2
        rows.append(row)
        print(f"[ok] {name}")

    savings = [1 - r["w64"]["faces"] / r["w64"]["faces_naive"] for r in rows]
    sizes64 = [r["w64"]["glb_bytes"] for r in rows]
    sizes128 = [r["w128"]["glb_bytes"] for r in rows]
    de16 = [r["k16_delta_e"] for r in rows]
    neon = np.array([r["neon_index"] for r in rows])
    hstd = np.array([r["w64"]["height_std"] for r in rows])
    r_pearson = float(np.corrcoef(neon, hstd)[0, 1])
    ssims = [r["ssim_w64"] for r in rows]

    hyp = [
        ("H1", "Culling spart bei W=64 je Quelle >= 80 % der Flaechen",
         min(savings) >= 0.80, f"min {min(savings):.1%}, max {max(savings):.1%}"),
        ("H2", "W=64 < 2 MB fuer alle, W=128 > 2 MB fuer mind. eine",
         max(sizes64) < MB2 and max(sizes128) > MB2,
         f"W=64 max {max(sizes64) / 1e6:.2f} MB, W=128 max {max(sizes128) / 1e6:.2f} MB"),
        ("H3", "K=16: mittleres Delta-E76 < 10 fuer jede Quelle",
         max(de16) < 10, f"max {max(de16):.2f}, min {min(de16):.2f}"),
        ("H4", "Pearson r(Neon-Index, Hoehenstreuung) > 0.5",
         r_pearson > 0.5, f"r = {r_pearson:.3f} (n = {len(rows)})"),
        ("H5", "SSIM Draufsicht W=64 vs. Quelle >= 0.5 fuer jede Quelle",
         min(ssims) >= 0.5, f"min {min(ssims):.3f}, max {max(ssims):.3f}"),
        ("H6", "Byte-identische GLB bei Wiederholung",
         all(r["deterministic"] for r in rows), f"{sum(r['deterministic'] for r in rows)}/{len(rows)} identisch"),
    ]
    # ---------------------------------------------------------------- Phase 2: Holdout
    final = P2VParams(width=96, colors=32)
    hold = []
    for src in sorted((ROOT / "p2v" / "holdout").iterdir()):
        img = load_frame(src)
        st = convert(src, tmp / "h.glb", final)
        hold.append({"source": src.name, "size": f"{img.width}x{img.height}", "ssim": round(topdown_ssim(img, final), 4),
                     "delta_e": st.delta_e_mean, "glb_bytes": st.glb_bytes})
    hyp += [
        ("H7", "Holdout, W=96 K=32: SSIM >= 0.5 fuer jedes Bild",
         min(h["ssim"] for h in hold) >= 0.5, f"min {min(h['ssim'] for h in hold):.3f} (n = {len(hold)})"),
        ("H8", "Holdout, K=32: Delta-E76 < 10 fuer jedes Bild",
         max(h["delta_e"] for h in hold) < 10, f"max {max(h['delta_e'] for h in hold):.2f}"),
        ("H9", "Holdout, W=96 K=32: GLB < 2 MB fuer jedes Bild",
         max(h["glb_bytes"] for h in hold) < MB2, f"max {max(h['glb_bytes'] for h in hold) / 1e6:.2f} MB"),
    ]
    out = {"rows": rows, "holdout": hold, "hypotheses": [{"id": i, "claim": c, "supported": bool(s), "evidence": e} for i, c, s, e in hyp]}
    (ROOT / "p2v" / "experiments.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md = ["# Pixel2Voxel – Experimente", "",
          "Generiert von `tools/p2v_experiments.py`. Kriterien sind vorab im Code fixiert.", "",
          "## Hypothesen", "", "| ID | Behauptung | Ergebnis | Evidenz |", "|---|---|---|---|"]
    md += [f"| {i} | {c} | {'belegt' if s else 'widerlegt'} | {e} |" for i, c, s, e in hyp]
    md += ["", "## Messwerte je Quelle", "",
           "| Werk | Neon | GLB W=64 | Culling | Hoehe sd | dE K=8 | dE K=16 | dE K=32 | SSIM W=32 | SSIM W=64 |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for r, sv in zip(rows, savings):
        md.append(f"| {r['name']} | {r['neon_index']:.2f} | {r['w64']['glb_bytes'] / 1e6:.2f} MB | {sv:.1%} | "
                  f"{r['w64']['height_std']:.2f} | {r['k8_delta_e']:.1f} | {r['k16_delta_e']:.1f} | "
                  f"{r['k32_delta_e']:.1f} | {r['ssim_w32']:.3f} | {r['ssim_w64']:.3f} |")
    md += ["", "## Dateigroesse nach Rasterbreite", "", "| Werk | W=32 | W=64 | W=96 | W=128 |", "|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['name']} | " + " | ".join(f"{r[f'w{w}']['glb_bytes'] / 1e6:.2f} MB" for w in (32, 64, 96, 128)) + " |")
    md += ["", "## Phase 2: Holdout (W=96, K=32)", "", "| Bild | Groesse | SSIM | dE | GLB |", "|---|---|---|---|---|"]
    md += [f"| {h['source']} | {h['size']} | {h['ssim']:.3f} | {h['delta_e']:.2f} | {h['glb_bytes'] / 1e6:.2f} MB |" for h in hold]
    (ROOT / "p2v" / "EXPERIMENTS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    for i, c, s, e in hyp:
        print(f"{i} {'BELEGT   ' if s else 'WIDERLEGT'} {c}  [{e}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
