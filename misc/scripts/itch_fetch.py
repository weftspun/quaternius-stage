"""Fetch the itch.io-only Quaternius mega-kits' FBX via the itch.io server API.

The 11 mega-kits aren't on Google Drive — their quaternius.com pages link to itch.io.
itch requires an API key (free: https://itch.io/user/settings/api-keys). Flow per game:
  GET  /games/<game_id>/uploads          -> pick the FBX zip (topology-preserving)
  GET  /uploads/<upload_id>/download     -> signed url -> download zip -> extract *.fbx
Extracted FBX land in <out>/<pack>/FBX/, so convert_all.sh converts them like the rest.

    export ITCH_API_KEY=...
    pixi run python itch_fetch.py itch_manifest.parquet _dl        # all 11
    pixi run python itch_fetch.py itch_manifest.parquet _dl downtowncitymegakit
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

API = "https://api.itch.io"


def _get(url: str, tries: int = 5) -> bytes:
    delay = 2.0
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.read()
        except Exception as e:  # 429/5xx/transient
            if attempt == tries - 1:
                raise
            print(f"  retry ({e}); sleeping {delay:.0f}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 60)


def uploads(game_id: str, key: str) -> list[dict]:
    data = json.loads(_get(f"{API}/games/{game_id}/uploads?api_key={key}"))
    return data.get("uploads", [])


def pick_fbx(ups: list[dict]) -> dict | None:
    """Prefer an upload whose filename says FBX; else a lone zip (extract FBX from it)."""
    fbx = [u for u in ups if "fbx" in u.get("filename", "").lower()]
    if fbx:
        return fbx[0]
    zips = [u for u in ups if u.get("filename", "").lower().endswith(".zip")]
    return zips[0] if len(zips) == 1 else None


def download_zip(upload_id, key: str, dest: Path) -> None:
    # The /download endpoint either returns JSON {"url": ...} or (following the
    # redirect) the file bytes directly. A zip starts with "PK\x03\x04".
    resp = _get(f"{API}/uploads/{upload_id}/download?api_key={key}")
    if resp[:2] == b"PK":
        data = resp
    else:
        data = _get(json.loads(resp)["url"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def extract_fbx(zip_path: Path, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    n, seen = 0, {}
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".fbx"):
                continue
            if "unreal" in info.filename.lower():
                continue  # skip the redundant "FBX (Unreal Engine)" axis-variant exports
            base = Path(info.filename).name
            if base in seen:  # disambiguate collisions across the zip's subfolders
                parent = Path(info.filename).parent.name
                base = f"{base[:-4]}__{parent}.fbx"
            seen[base] = True
            (out_dir / base).write_bytes(z.read(info))
            n += 1
    return n


def main() -> None:
    key = os.environ.get("ITCH_API_KEY")
    if not key:
        raise SystemExit("set ITCH_API_KEY (free: itch.io/user/settings/api-keys)")

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    manifest, out_dir = args[0], Path(args[1])
    only = args[2] if len(args) > 2 else None
    tmp = Path("_itch")

    import pandas as pd

    ok = fail = skip = 0
    for r in pd.read_parquet(manifest).itertuples(index=False):
        pack, slug, gid = r.pack, r.slug, str(r.game_id)
        if not gid or gid == "nan":
            continue
        if only and pack != only:
            continue
        fbx_dir = out_dir / pack / "FBX"
        if fbx_dir.exists() and list(fbx_dir.glob("*.fbx")):
            print(f"SKIP {pack} (have fbx)", flush=True)
            skip += 1
            continue
        try:
            up = pick_fbx(uploads(gid, key))
            if not up:
                print(f"FAIL {pack} (no fbx/zip upload)", flush=True)
                fail += 1
                continue
            zp = tmp / f"{pack}.zip"
            print(f"==== {pack}: {up['filename']} ({up.get('size', 0)//1024} KB) ====", flush=True)
            download_zip(up["id"], key, zp)
            count = extract_fbx(zp, fbx_dir)
            zp.unlink(missing_ok=True)
            print(f"  extracted {count} fbx", flush=True)
            ok += 1 if count else 0
            fail += 0 if count else 1
        except Exception as e:
            print(f"FAIL {pack}: {e}", flush=True)
            fail += 1

    print(f"\nDONE fetched={ok} skipped={skip} failed={fail}")


if __name__ == "__main__":
    main()
