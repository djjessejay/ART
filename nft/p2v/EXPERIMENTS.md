# Pixel2Voxel – Experimente

Generiert von `tools/p2v_experiments.py`. Kriterien sind vorab im Code fixiert.

## Hypothesen

| ID | Behauptung | Ergebnis | Evidenz |
|---|---|---|---|
| H1 | Culling spart bei W=64 je Quelle >= 80 % der Flaechen | belegt | min 81.1%, max 90.2% |
| H2 | W=64 < 2 MB fuer alle, W=128 > 2 MB fuer mind. eine | belegt | W=64 max 0.77 MB, W=128 max 3.14 MB |
| H3 | K=16: mittleres Delta-E76 < 10 fuer jede Quelle | widerlegt | max 12.09, min 1.58 |
| H4 | Pearson r(Neon-Index, Hoehenstreuung) > 0.5 | widerlegt | r = 0.379 (n = 11) |
| H5 | SSIM Draufsicht W=64 vs. Quelle >= 0.5 fuer jede Quelle | widerlegt | min 0.367, max 0.864 |
| H6 | Byte-identische GLB bei Wiederholung | belegt | 11/11 identisch |
| H7 | Holdout, W=96 K=32: SSIM >= 0.5 fuer jedes Bild | belegt | min 0.534 (n = 5) |
| H8 | Holdout, K=32: Delta-E76 < 10 fuer jedes Bild | belegt | max 6.49 |
| H9 | Holdout, W=96 K=32: GLB < 2 MB fuer jedes Bild | belegt | max 1.75 MB |

## Messwerte je Quelle

| Werk | Neon | GLB W=64 | Culling | Hoehe sd | dE K=8 | dE K=16 | dE K=32 | SSIM W=32 | SSIM W=64 |
|---|---|---|---|---|---|---|---|---|---|
| Bern Polka Express [P2V] | 0.35 | 0.56 MB | 84.2% | 1.35 | 12.8 | 10.6 | 8.3 | 0.218 | 0.417 |
| Zuerisee Dub [P2V] | 0.29 | 0.55 MB | 83.6% | 1.29 | 13.9 | 11.0 | 8.8 | 0.248 | 0.439 |
| Pixel Signature [P2V] | 0.28 | 0.47 MB | 90.2% | 2.91 | 14.2 | 10.4 | 7.4 | 0.309 | 0.625 |
| @R† Seal [P2V] | 0.00 | 0.73 MB | 89.8% | 0.84 | 2.2 | 1.6 | 1.2 | 0.793 | 0.864 |
| Vinyl Roots [P2V] | 0.02 | 0.53 MB | 82.5% | 1.33 | 6.5 | 4.8 | 3.7 | 0.389 | 0.587 |
| BSS Genre Router [P2V] | 0.11 | 0.62 MB | 85.1% | 1.36 | 14.5 | 11.8 | 9.7 | 0.146 | 0.367 |
| Logo Codex [P2V] | 0.15 | 0.64 MB | 89.9% | 2.86 | 12.5 | 10.0 | 6.9 | 0.229 | 0.494 |
| Test Lab | 0.15 | 0.73 MB | 86.6% | 1.74 | 11.0 | 5.4 | 3.7 | 0.542 | 0.721 |
| DJJJ Signature Bridge v1 | 0.03 | 0.77 MB | 81.1% | 0.81 | 5.6 | 4.5 | 3.1 | 0.349 | 0.536 |
| Neon Drive [P2V] | 0.21 | 0.50 MB | 83.6% | 1.31 | 10.8 | 7.1 | 5.7 | 0.353 | 0.524 |
| Mythos Jr. [P2V] | 0.15 | 0.61 MB | 86.5% | 1.25 | 15.2 | 12.1 | 9.7 | 0.160 | 0.368 |

## Dateigroesse nach Rasterbreite

| Werk | W=32 | W=64 | W=96 | W=128 |
|---|---|---|---|---|
| Bern Polka Express [P2V] | 0.15 MB | 0.56 MB | 1.24 MB | 2.36 MB |
| Zuerisee Dub [P2V] | 0.15 MB | 0.55 MB | 1.20 MB | 2.27 MB |
| Pixel Signature [P2V] | 0.13 MB | 0.47 MB | 0.97 MB | 1.66 MB |
| @R† Seal [P2V] | 0.20 MB | 0.73 MB | 1.60 MB | 3.09 MB |
| Vinyl Roots [P2V] | 0.14 MB | 0.53 MB | 1.11 MB | 1.90 MB |
| BSS Genre Router [P2V] | 0.16 MB | 0.62 MB | 1.36 MB | 2.64 MB |
| Logo Codex [P2V] | 0.18 MB | 0.64 MB | 1.38 MB | 2.56 MB |
| Test Lab | 0.21 MB | 0.73 MB | 1.59 MB | 2.96 MB |
| DJJJ Signature Bridge v1 | 0.20 MB | 0.77 MB | 1.65 MB | 3.14 MB |
| Neon Drive [P2V] | 0.13 MB | 0.50 MB | 1.08 MB | 1.85 MB |
| Mythos Jr. [P2V] | 0.16 MB | 0.61 MB | 1.37 MB | 2.61 MB |

## Phase 2: Holdout (W=96, K=32)

| Bild | Groesse | SSIM | dE | GLB |
|---|---|---|---|---|
| asimov-law1.jpg | 2752x1536 | 0.630 | 4.49 | 1.13 MB |
| asimov-law2.jpg | 2752x1536 | 0.600 | 2.47 | 1.10 MB |
| asimov-law3.jpg | 2752x1536 | 0.601 | 1.61 | 1.19 MB |
| asimov-shield-kernel.jpg | 512x286 | 0.534 | 1.85 | 1.03 MB |
| globe-thumb.jpg | 125x126 | 0.842 | 6.49 | 1.75 MB |
