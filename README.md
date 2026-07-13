# quaternius-stage

OpenUSD (`.usda`) copy of [Quaternius](https://quaternius.com) CC0 low-poly packs — converted from **FBX** (topology-preserving; glTF triangulates), n-gon/quad topology kept.

Conventions (verified): **Y-up, −Z forward, right-handed, real-world meters**. Keyed by ETNF `asset_uuid` in `quaternius.parquet`, natural key `quaternius:<pack>/<model>`.

## Layout
- `models/<pack>/<Model>.usda` — the meshes
- `quaternius.parquet` — ETNF catalog (one row per model)
- `drive_manifest.tsv` — every pack → its Google Drive folder id (71/82 resolved)
- `fbx_to_usda_batch.py` — Blender ufbx → `.usda`
- `fetch_convert_all.sh` — resumable: gdown each folder, convert its FBX
- `build_etnf.py` — build the parquet

## Rebuild
Quaternius serves each pack as a public Google Drive folder. Two fetchers:

**Preferred — official Drive API** (pixi; pagination + backoff, robust vs rate limits). Auth with a service account (`GOOGLE_APPLICATION_CREDENTIALS`) or an API key (`GOOGLE_API_KEY`) — the project needs *Google Drive API* enabled:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json   # or GOOGLE_API_KEY=AIza...
pixi run python drive_fetch.py drive_manifest.tsv _dl          # FBX only, resumable
blender -b --factory-startup --python fbx_to_usda_batch.py -- _dl/<pack>/FBX models/<pack>
py -3 build_etnf.py models drive_manifest.tsv quaternius.parquet
```

**Fallback — gdown** (no key, but Drive rate-limits bulk pulls):
```bash
bash fetch_convert_all.sh drive_manifest.tsv _dl   # resumable
```
11 mega-kits load their link differently and aren't in the manifest yet.

License: **CC0-1.0** (Quaternius / @Quaternius). See `LICENSE`.
