#!/usr/bin/env bash
# Fetch every Quaternius pack's Google Drive folder, convert its FBX (topology-
# preserving; glTF triangulates) to ASCII OpenUSD, namespaced per pack.
#
# Resumable: a pack whose models/<pack>/ already has .usda is skipped.
# Usage: bash fetch_convert_all.sh <manifest.tsv> <workdir>
set -u

MANIFEST="${1:-drive_manifest.tsv}"
WORK="${2:-_dl}"
GDOWN="/c/Users/ernes/AppData/Roaming/Python/Python314/Scripts/gdown.exe"
CONVERT="$(dirname "$0")/fbx_to_usda_batch.py"
mkdir -p "$WORK"

done=0; skipped=0; failed=""
while IFS=$'\t' read -r name fid; do
  [ -z "${fid:-}" ] && { echo "NO-FOLDER $name"; failed="$failed $name(no-folder)"; continue; }
  out="models/$name"
  if [ -d "$out" ] && ls "$out"/*.usda >/dev/null 2>&1; then
    echo "SKIP $name (already converted)"; skipped=$((skipped+1)); continue
  fi
  echo "==== $name ($fid) ===="
  rm -rf "${WORK:?}/$name"
  "$GDOWN" --folder "https://drive.google.com/drive/folders/$fid" -O "$WORK/$name" -q 2>&1 | tail -2
  fbxdir="$WORK/$name/FBX"
  [ -d "$fbxdir" ] || fbxdir="$(find "$WORK/$name" -type d -iname fbx | head -1)"
  if [ -z "$fbxdir" ] || ! ls "$fbxdir"/*.fbx >/dev/null 2>&1; then
    echo "FAIL $name (no FBX dir)"; failed="$failed $name(no-fbx)"; continue
  fi
  mkdir -p "$out"
  blender --background --factory-startup --python "$CONVERT" -- "$fbxdir" "$out" 2>&1 | grep -E "CONVERTED|FAIL" | tail -3
  ls "$out"/*.usda >/dev/null 2>&1 && done=$((done+1)) || { echo "FAIL $name (no usda out)"; failed="$failed $name(no-usda)"; }
  rm -rf "${WORK:?}/$name"   # reclaim space (OBJ/Blend/glTF not needed)
done < "$MANIFEST"

echo "================================"
echo "DONE converted=$done skipped=$skipped"
echo "FAILED:$failed"
