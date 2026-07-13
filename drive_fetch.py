"""Download Quaternius pack FBX from Google Drive via the official Drive API v3.

Robust where gdown isn't: real pagination + exponential backoff on the rate-limit
(403 userRateLimitExceeded / 429) that gdown's scraping trips on. Quaternius folders
are shared "anyone with the link", so a plain **API key** suffices — no OAuth.

Set a key (free: console.cloud.google.com -> enable "Google Drive API" -> API key):
    export GOOGLE_API_KEY=AIza...            # or pass --api-key

Usage:
    pixi run python drive_fetch.py drive_manifest.tsv _dl        # all packs, FBX only
    pixi run python drive_fetch.py drive_manifest.tsv _dl cars   # one pack

Resumable: a pack whose out/<pack>/*.fbx already exist is skipped. Only the FBX
subfolder is fetched (topology-preserving; glTF triangulates, .blend is huge).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

FOLDER_MIME = "application/vnd.google-apps.folder"
_RETRY_STATUS = {403, 429, 500, 502, 503, 504}


def _service(api_key: str):
    # cache_discovery=False avoids a noisy warning on 3.12+.
    return build("drive", "v3", developerKey=api_key, cache_discovery=False)


def _with_backoff(request, what: str, tries: int = 6):
    """Execute a Drive request, backing off on transient/rate-limit errors."""
    delay = 2.0
    for attempt in range(tries):
        try:
            return request.execute()
        except HttpError as e:
            status = getattr(e.resp, "status", None)
            if status in _RETRY_STATUS and attempt < tries - 1:
                print(f"  rate/err {status} on {what}; sleeping {delay:.0f}s", flush=True)
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise


def list_children(svc, folder_id: str) -> list[dict]:
    out, token = [], None
    while True:
        resp = _with_backoff(
            svc.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=1000,
                pageToken=token,
            ),
            f"list {folder_id}",
        )
        out.extend(resp.get("files", []))
        token = resp.get("nextPageToken")
        if not token:
            return out


def find_fbx_files(svc, pack_folder_id: str) -> list[dict]:
    """Return the .fbx files under the pack's FBX subfolder (or the pack root if flat)."""
    children = list_children(svc, pack_folder_id)
    fbx_dirs = [c for c in children if c["mimeType"] == FOLDER_MIME and c["name"].lower() == "fbx"]
    search_id = fbx_dirs[0]["id"] if fbx_dirs else pack_folder_id
    files = list_children(svc, search_id) if fbx_dirs else children
    return [f for f in files if f["name"].lower().endswith(".fbx")]


def download(svc, file_id: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = svc.files().get_media(fileId=file_id)
    with open(dest, "wb") as fh:
        dl = MediaIoBaseDownload(fh, req, chunksize=8 * 1024 * 1024)
        done = False
        delay = 2.0
        while not done:
            try:
                _, done = dl.next_chunk()
            except HttpError as e:
                if getattr(e.resp, "status", None) in _RETRY_STATUS:
                    print(f"  rate/err on chunk {dest.name}; sleeping {delay:.0f}s", flush=True)
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                    continue
                raise


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--api-key=")]
    key = os.environ.get("GOOGLE_API_KEY") or next(
        (a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--api-key=")), None
    )
    if not key:
        raise SystemExit("set GOOGLE_API_KEY (or --api-key=...) — a Drive-API-enabled key")

    manifest, out_dir = args[0], Path(args[1])
    only = args[2] if len(args) > 2 else None
    svc = _service(key)

    fetched = skipped = failed = 0
    for line in Path(manifest).read_text().splitlines():
        parts = line.rstrip("\n").split("\t")
        if len(parts) != 2 or not parts[1]:
            continue
        pack, fid = parts
        if only and pack != only:
            continue
        dest_dir = out_dir / pack / "FBX"
        if dest_dir.exists() and list(dest_dir.glob("*.fbx")):
            print(f"SKIP {pack} (have fbx)", flush=True)
            skipped += 1
            continue
        try:
            fbx = find_fbx_files(svc, fid)
            if not fbx:
                print(f"FAIL {pack} (no fbx found)", flush=True)
                failed += 1
                continue
            print(f"==== {pack}: {len(fbx)} fbx ====", flush=True)
            for f in fbx:
                download(svc, f["id"], dest_dir / f["name"])
            fetched += 1
        except Exception as e:  # keep the corpus run going
            print(f"FAIL {pack}: {e}", flush=True)
            failed += 1

    print(f"\nDONE fetched={fetched} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
