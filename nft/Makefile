.PHONY: all retouch analyze assets metadata metadata-strict test pin deploy-testnet clean

PY ?= python3

all: analyze assets metadata

retouch:            ## Wave-II-Retusche -> assets/retouched
	$(PY) tools/retouch.py

analyze:            ## Bildanalyse -> analysis.json
	$(PY) tools/analyze.py

assets:             ## Mint-Assets (Crop, GIF-Poster, Banner) -> assets/clean
	$(PY) tools/prepare_assets.py

metadata: assets    ## ERC-721 Metadaten (Platzhalter-CID erlaubt)
	$(PY) tools/build_metadata.py

metadata-strict: assets  ## Gate fuer Mainnet: keine Platzhalter
	$(PY) tools/build_metadata.py --strict

test:               ## Foundry-Tests inkl. Fuzzing
	cd contracts && forge test -vv

pin:                ## Zwei-Stufen-Pinning ueber lokale Kubo-Node
	bash tools/pin.sh

deploy-testnet:     ## Base Sepolia, Signatur per Ledger
	cd contracts && forge script script/Deploy.s.sol --rpc-url base_sepolia --ledger --sender $$OWNER --broadcast --verify

clean:
	rm -rf build assets/clean contracts/out contracts/cache
