#!/usr/bin/env bash
# Downloads REAL data only. Integrity-checks the Zenodo files against published md5.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/raw outputs
Z=https://zenodo.org/records/15354599/files
declare -A MD5=(
 [allBridge_data.parquet]=f485bc1cf6817596ba2ea6fab87e94f2
 [connext_data.parquet]=8271df21b9ebf9060c23adeb32fc355e
 [orbitChain_data.parquet]=a280cabef9242e62e7e66a5f65b83212
 [wormhole_data.parquet]=a657d7cc9d0eb6126bae29ea77552d60
 [block_data.parquet]=3abb385181017a170883b14b5f60ddfb
 [readme.md]=e0319521e9a2868eba5b95b0d94f8387
)
for f in "${!MD5[@]}"; do
  [ -s "data/raw/$f" ] || wget -q --show-progress -O "data/raw/$f" "$Z/$f?download=1"
  got=$(md5sum "data/raw/$f" | cut -d' ' -f1)
  if [ "$got" = "${MD5[$f]}" ]; then echo "OK   $f"; else echo "FAIL $f (got $got)"; fi
done | tee outputs/download_integrity.txt
# OFAC SDN digital-currency addresses (0xB10C mirror of the US Treasury list)
wget -q -O data/raw/sanctioned_addresses_ETH.txt \
  https://raw.githubusercontent.com/0xB10C/ofac-sanctioned-digital-currency-addresses/lists/sanctioned_addresses_ETH.txt || echo "OFAC list download failed (optional)"
wc -l data/raw/sanctioned_addresses_ETH.txt 2>/dev/null | tee -a outputs/download_integrity.txt || true
echo "Done. If any file says FAIL, re-run or re-download that file."
