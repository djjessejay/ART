#!/usr/bin/env bash
# IPFS-Pinning in zwei Stufen ueber eine LOKALE Kubo-Node.
#
#   Stufe 1: assets/clean  -> IMAGES_CID   (Bilder, GIF, Banner)
#   Stufe 2: build/        -> METADATA_CID (metadata/<id>.json + collection.json)
#
# Sicherheit:
#   - Kubo-API nur auf 127.0.0.1:5001 (niemals oeffentlich exponieren).
#     Pruefen: ipfs config Addresses.API  -> /ip4/127.0.0.1/tcp/5001
#   - Optionaler Remote-Pinning-Service (z. B. Pinata) ueber Kubo "pin remote",
#     Token liegt im Kubo-Keystore, nicht in diesem Repo.
#   - CIDv1 + raw-leaves fuer stabile, gateway-freundliche CIDs.
set -euo pipefail

cd "$(dirname "$0")/.."
command -v ipfs >/dev/null || { echo "kubo (ipfs) nicht installiert"; exit 1; }

api="$(ipfs config Addresses.API)"
case "$api" in
  /ip4/127.0.0.1/*|/ip6/::1/*) ;;
  *) echo "ABBRUCH: Kubo-API ist nicht auf localhost gebunden ($api)"; exit 1 ;;
esac

add_dir() { ipfs add -Q -r --cid-version=1 --raw-leaves --pin=true "$1"; }

echo "[1/4] Assets vorbereiten"
python3 tools/prepare_assets.py

echo "[2/4] Bilder pinnen"
IMAGES_CID="$(add_dir assets/clean)"
echo "      IMAGES_CID=$IMAGES_CID"
printf '{\n  "images": "%s"\n}\n' "$IMAGES_CID" > cids.json

echo "[3/4] Metadaten bauen (strict)"
python3 tools/build_metadata.py --strict

echo "[4/4] Metadaten pinnen"
METADATA_CID="$(add_dir build)"
printf '{\n  "images": "%s",\n  "metadata": "%s"\n}\n' "$IMAGES_CID" "$METADATA_CID" > cids.json
echo "      METADATA_CID=$METADATA_CID"

if [[ -n "${IPFS_REMOTE_SERVICE:-}" ]]; then
  ipfs pin remote add --service="$IPFS_REMOTE_SERVICE" --name=bdg-images "$IMAGES_CID"
  ipfs pin remote add --service="$IPFS_REMOTE_SERVICE" --name=bdg-metadata "$METADATA_CID"
fi

cat <<EOF

Fertig. Fuer das Deployment:
  export METADATA_CID=$METADATA_CID
  Pruefung: ipfs cat $METADATA_CID/metadata/1.json
EOF
