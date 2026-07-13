#!/usr/bin/env bash
# Convert every fetched pack's FBX -> ASCII OpenUSD (Blender ufbx), namespaced per pack.
# Resumable: a pack whose models/<pack>/*.usda already exist is skipped.
# Usage: bash convert_all.sh <dl_dir>
set -u
DL="${1:-_dl}"
CONVERT="$(dirname "$0")/fbx_to_usda_batch.py"
done=0; skipped=0; failed=""
for fbxdir in "$DL"/*/FBX; do
  [ -d "$fbxdir" ] || continue
  ls "$fbxdir"/*.fbx >/dev/null 2>&1 || continue
  pack="$(basename "$(dirname "$fbxdir")")"
  out="models/$pack"
  if [ -d "$out" ] && ls "$out"/*.usda >/dev/null 2>&1; then
    echo "SKIP $pack"; skipped=$((skipped+1)); continue
  fi
  mkdir -p "$out"
  echo "==== $pack ===="
  blender --background --factory-startup --python "$CONVERT" -- "$fbxdir" "$out" 2>&1 | grep -E "CONVERTED|FAIL" | tail -2
  ls "$out"/*.usda >/dev/null 2>&1 && done=$((done+1)) || failed="$failed $pack"
done
echo "================ DONE converted=$done skipped=$skipped FAILED:$failed"
