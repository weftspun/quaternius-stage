"""Build the ETNF parquet catalog for the Quaternius OpenUSD assets.

Essential Tuple Normal Form: one 1:1 relation keyed by a UUIDv5 `asset_uuid`, derived
from a stable natural key. Keys are byte-compatible with the vsk-session-item-recommendation
lake (same namespace + `asset:<natural_key>` rule), so this catalog joins that lake directly.
Quaternius has many packs that reuse model names (Fence, Tree, ...), so the natural key is
namespaced by pack: `quaternius:<pack>/<model>`.

Usage: python build_etnf.py <models_dir> <drive_manifest.tsv> <out.parquet>
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pandas as pd

# Fixed lake namespace (identical to vsk_recsys/data/etnf.py) so keys line up.
NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL,
    "https://github.com/V-Sekai-fire/vsk-session-item-recommendation-01",
)

SOURCE = "quaternius.com"
LICENSE = "CC0-1.0"


def asset_uuid(natural_key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"asset:{natural_key}"))


def build(models_dir: str, manifest_file: str, out: str) -> pd.DataFrame:
    folder_by_pack = {}
    for line in Path(manifest_file).read_text().splitlines():
        parts = line.rstrip("\n").split("\t")
        if len(parts) == 2 and parts[1]:
            folder_by_pack[parts[0]] = f"https://drive.google.com/drive/folders/{parts[1]}"

    rows = []
    for usd in sorted(Path(models_dir).glob("*/*.usda")):
        pack = usd.parent.name
        model = usd.stem
        natural_key = f"quaternius:{pack}/{model}"
        rows.append(
            {
                "asset_uuid": asset_uuid(natural_key),
                "natural_key": natural_key,
                "pack": pack,
                "name": model,
                "usd_file": f"models/{pack}/{model}.usda",
                "source": SOURCE,
                "source_folder_url": folder_by_pack.get(pack, ""),
                "pack_page_url": f"https://quaternius.com/packs/{pack}.html",
                "up_axis": "Y",
                "forward_axis": "-Z",
                "handedness": "right",
                "meters_per_unit": 1.0,
                "license": LICENSE,
            }
        )

    frame = pd.DataFrame(rows)
    if frame["asset_uuid"].nunique() != len(frame):
        raise SystemExit("PK collision: asset_uuid not unique")
    frame.to_parquet(out, index=False)
    print(f"wrote {out}: {len(frame)} assets across {frame['pack'].nunique()} packs, PK-unique")
    print(frame[["natural_key", "up_axis", "handedness"]].head(3).to_string(index=False))
    return frame


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2], sys.argv[3])
