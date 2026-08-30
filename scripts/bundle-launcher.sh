#!/usr/bin/env bash
set -euo pipefail

BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FEATURE_DATA="${CONTROL_DECK_FEATURE_DATA_DIR:?CONTROL_DECK_FEATURE_DATA_DIR is required}"
SHARED_CACHE="${CONTROL_DECK_SHARED_CACHE_DIR:?CONTROL_DECK_SHARED_CACHE_DIR is required}"

export MEDIA_FORGE_DATA_DIR="${MEDIA_FORGE_DATA_DIR:-$FEATURE_DATA/data}"
export MEDIA_FORGE_CONTROLDECK_URL="${MEDIA_FORGE_CONTROLDECK_URL:-${CONTROL_DECK_BASE_URL:-http://127.0.0.1:8765}}"
export MEDIA_FORGE_IMAGE_RUNTIME_PYTHON="${MEDIA_FORGE_IMAGE_RUNTIME_PYTHON:-$FEATURE_DATA/runtimes/rocm-torch/.venv/bin/python}"
# 動画は画像と別の venv を使う。同じものに載せると、片方の pin を動かした
# ときにもう片方が黙って壊れる。
export MEDIA_FORGE_VIDEO_RUNTIME_PYTHON="${MEDIA_FORGE_VIDEO_RUNTIME_PYTHON:-$FEATURE_DATA/runtimes/wan21-t2v/.venv/bin/python}"
# Wan 2.2 は上流の wan package を要する。場所を渡さないと本番では動かせない。
export MEDIA_FORGE_WAN_SOURCE_ROOT="${MEDIA_FORGE_WAN_SOURCE_ROOT:-$FEATURE_DATA/runtimes/wan2.2-source}"
export MEDIA_FORGE_ENV_STATUS_FILE="${MEDIA_FORGE_ENV_STATUS_FILE:-$FEATURE_DATA/environment-status.json}"
export HF_HOME="${HF_HOME:-$SHARED_CACHE/huggingface}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$SHARED_CACHE/pip}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$SHARED_CACHE/uv}"
export AMD_COMGR_CACHE="${AMD_COMGR_CACHE:-1}"
export AMD_COMGR_CACHE_DIR="${AMD_COMGR_CACHE_DIR:-$SHARED_CACHE/rocm/comgr}"
export MIOPEN_CUSTOM_CACHE_DIR="${MIOPEN_CUSTOM_CACHE_DIR:-$SHARED_CACHE/rocm/miopen-kernel}"
export MIOPEN_USER_DB_PATH="${MIOPEN_USER_DB_PATH:-$SHARED_CACHE/rocm/miopen-db}"
export HF_ENABLE_PARALLEL_LOADING="${HF_ENABLE_PARALLEL_LOADING:-YES}"
mkdir -p "$MEDIA_FORGE_DATA_DIR" "$FEATURE_DATA/runtimes" "$HF_HOME" "$PIP_CACHE_DIR" \
  "$AMD_COMGR_CACHE_DIR" "$MIOPEN_CUSTOM_CACHE_DIR" "$MIOPEN_USER_DB_PATH"

case "${1:-}" in
  doctor|provision|serve)
    exec "$BUNDLE_ROOT/bin/mediaforge-core" "$1"
    ;;
  *)
    printf 'usage: mediaforge {doctor|provision|serve}\n' >&2
    exit 2
    ;;
esac
