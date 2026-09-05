#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$REPO_ROOT/.venv"
RUNTIME_ROOT="$REPO_ROOT/runtimes"
CONFIG_FILE="$REPO_ROOT/config/config.yaml"
ENV_STATUS_FILE="$REPO_ROOT/config/environment-status.json"
PYTHON_BIN="${PYTHON_BIN:-python3}"

info() { printf '\033[36m[mf]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[mf] warning:\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31m[mf] error:\033[0m %s\n' "$*" >&2; exit 1; }

check_root() {
  [ "$(id -u)" -ne 0 ] || die "do not run Media Forge as root"
}

check_python() {
  command -v "$PYTHON_BIN" >/dev/null || die "$PYTHON_BIN was not found"
  "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
    || die "Python 3.11 or newer is required"
}

yaml_scalar() {
  local file="$1" key="$2"
  [ -f "$file" ] || return 1
  sed -n "s/^${key}:[[:space:]]*//p" "$file" | head -1 | tr -d '"'\'' '
}

expand_home() {
  local value="$1"
  case "$value" in
    "~"*) printf '%s\n' "$HOME${value#\~}" ;;
    *) printf '%s\n' "$value" ;;
  esac
}

media_data_dir() {
  local value=""
  if [ -n "${MEDIA_FORGE_DATA_DIR:-}" ]; then
    printf '%s\n' "$MEDIA_FORGE_DATA_DIR"
    return
  fi
  value="$(yaml_scalar "$CONFIG_FILE" data_dir || true)"
  [ -n "$value" ] || value="$HOME/.local/share/control-deck-media-forge"
  expand_home "$value"
}

model_store_root() {
  local value=""
  if [ -n "${MEDIA_FORGE_MODEL_STORE_ROOT:-}" ]; then
    printf '%s\n' "$MEDIA_FORGE_MODEL_STORE_ROOT"
    return
  fi
  value="$(yaml_scalar "$CONFIG_FILE" model_store_root || true)"
  [ -n "$value" ] || value="$(media_data_dir)/models"
  expand_home "$value"
}

control_deck_config() {
  local candidate=""
  if [ -n "${CONTROL_DECK_CONFIG:-}" ]; then
    candidate="$CONTROL_DECK_CONFIG"
  elif [ -n "${CONTROL_DECK_REPO:-}" ]; then
    candidate="$CONTROL_DECK_REPO/config/config.yaml"
  elif [ -f "$REPO_ROOT/../ControlDeck/app/config/config.yaml" ]; then
    candidate="$REPO_ROOT/../ControlDeck/app/config/config.yaml"
  elif [ -f "$REPO_ROOT/../ControlDeck/config/config.yaml" ]; then
    candidate="$REPO_ROOT/../ControlDeck/config/config.yaml"
  fi
  [ -n "$candidate" ] && [ -r "$candidate" ] && printf '%s\n' "$candidate"
}

shared_cache_root() {
  local control_config control_data=""
  control_config="$(control_deck_config || true)"
  if [ -n "$control_config" ]; then
    control_data="$(yaml_scalar "$control_config" data_dir || true)"
  fi
  if [ -n "$control_data" ]; then
    printf '%s/cache\n' "$(expand_home "$control_data")"
  else
    warn "ControlDeck data_dir was not readable; using the Media Forge cache"
    printf '%s/cache\n' "$(media_data_dir)"
  fi
}

export_cache_paths() {
  local create="${1:-yes}" cache
  cache="$(shared_cache_root)"
  export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$cache/pip}"
  export UV_CACHE_DIR="${UV_CACHE_DIR:-$cache/uv}"
  export npm_config_cache="${npm_config_cache:-$cache/npm}"
  export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$cache/ms-playwright}"
  export HF_HOME="${HF_HOME:-$cache/huggingface}"
  export HF_ENABLE_PARALLEL_LOADING="${HF_ENABLE_PARALLEL_LOADING:-YES}"
  export AMD_COMGR_CACHE="${AMD_COMGR_CACHE:-1}"
  export AMD_COMGR_CACHE_DIR="${AMD_COMGR_CACHE_DIR:-$cache/rocm/comgr}"
  export MIOPEN_CUSTOM_CACHE_DIR="${MIOPEN_CUSTOM_CACHE_DIR:-$cache/rocm/miopen-kernel}"
  export MIOPEN_USER_DB_PATH="${MIOPEN_USER_DB_PATH:-$cache/rocm/miopen-db}"
  if [ "$create" = yes ]; then
    mkdir -p "$PIP_CACHE_DIR" "$UV_CACHE_DIR" "$npm_config_cache" \
      "$PLAYWRIGHT_BROWSERS_PATH" "$HF_HOME" "$AMD_COMGR_CACHE_DIR" \
      "$MIOPEN_CUSTOM_CACHE_DIR" "$MIOPEN_USER_DB_PATH" 2>/dev/null || true
  fi
}

safe_remove_venv() {
  local target="$1"
  case "$target" in
    "$VENV"|"$RUNTIME_ROOT"/*/.venv) rm -rf -- "$target" ;;
    *) die "refusing to remove unexpected venv path: $target" ;;
  esac
}

ensure_env() {
  local target="$1" requirements="$2" label="$3" install_mode="${4:-quiet}"
  local stamp="$target/.req-stamp" current
  [ -f "$requirements" ] || die "requirements file is missing: $requirements"
  if [ -e "$target" ] && ! "$target/bin/python" -c 'pass' >/dev/null 2>&1; then
    warn "$label environment is broken; rebuilding $target"
    safe_remove_venv "$target"
  fi
  if [ ! -x "$target/bin/python" ]; then
    info "creating $label environment: $target"
    "$PYTHON_BIN" -m venv "$target" || die "failed to create $label environment"
  fi
  current="$(sha256sum "$requirements" | cut -d' ' -f1)"
  if [ ! -f "$stamp" ] || [ "$(cat "$stamp")" != "$current" ]; then
    info "installing $label dependencies"
    "$target/bin/pip" install --quiet --upgrade pip
    if [ "$install_mode" = verbose ]; then
      "$target/bin/pip" install --progress-bar on -r "$requirements"
    else
      "$target/bin/pip" install --quiet -r "$requirements"
    fi
    printf '%s\n' "$current" > "$stamp"
  else
    info "$label requirements unchanged; skipping pip"
  fi
}

stamp_state() {
  local target="$1" requirements="$2" stamp current
  stamp="$target/.req-stamp"
  [ -x "$target/bin/python" ] || { printf 'missing'; return; }
  [ -f "$stamp" ] || { printf 'stale'; return; }
  current="$(sha256sum "$requirements" | cut -d' ' -f1)"
  [ "$(cat "$stamp")" = "$current" ] && printf 'current' || printf 'stale'
}

directory_bytes() {
  local target="$1"
  [ -e "$target" ] && du -sb "$target" 2>/dev/null | awk '{print $1}' || printf '0\n'
}

filesystem_probe_path() {
  local target="$1"
  while [ ! -e "$target" ] && [ "$target" != "/" ]; do
    target="$(dirname "$target")"
  done
  printf '%s\n' "$target"
}

model_library_state() {
  local registry_python="$PYTHON_BIN"
  [ ! -x "$VENV/bin/python" ] || registry_python="$VENV/bin/python"
  if rg -q '^model_libraries:[[:space:]]*\[[^]]+\]' "$CONFIG_FILE" 2>/dev/null; then
    printf 'ok'
  elif { [ -d "$HF_HOME/hub" ] || [ -d "$(model_store_root)/hub" ]; } && \
    PYTHONPATH="$REPO_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}" \
    "$registry_python" - "$(model_registry_manifest)" "$(model_catalog_manifest)" "$HF_HOME" \
      "$(model_store_root)" >/dev/null 2>&1 <<'PY'
import sys
from pathlib import Path

from mediaforge.models import ModelRegistry

models = ModelRegistry.load(
    Path(sys.argv[1]), catalog_manifest=Path(sys.argv[2]), hf_home=Path(sys.argv[3]),
    model_store_root=Path(sys.argv[4]),
).all()
raise SystemExit(0 if any(model.installed for model in models) else 1)
PY
  then
    printf 'ok'
  else
    printf 'missing'
  fi
}

auto_provision_enabled() {
  local value
  value="$(yaml_scalar "$CONFIG_FILE" auto_provision || true)"
  case "${value,,}" in
    true|yes|1) return 0 ;;
    false|no|0) return 1 ;;
    *) warn "auto_provision must be true or false; automatic runtime setup is disabled"; return 1 ;;
  esac
}

gpu_snapshot_state() {
  local snapshot="$RUNTIME_ROOT/rocm-torch/.gpu-check.json"
  [ -s "$snapshot" ] && printf 'ok' || printf 'checking'
}

write_environment_status() {
  local runtime_override="${1:-}" gpu_override="${2:-}" runtime_detail="${3:-}" gpu_detail="${4:-}"
  local core_state runtime_state gpu_state model_state available estimate
  core_state="$(stamp_state "$VENV" "$REPO_ROOT/requirements.txt")"
  runtime_state="$(stamp_state "$RUNTIME_ROOT/rocm-torch/.venv" "$RUNTIME_ROOT/rocm-torch/requirements.txt")"
  gpu_state="$(gpu_snapshot_state)"
  [ -z "$runtime_override" ] || runtime_state="$runtime_override"
  [ -z "$gpu_override" ] || gpu_state="$gpu_override"
  if [ "$runtime_state" != current ] && [ -z "$gpu_override" ]; then
    gpu_state="checking"
  fi
  model_state="$(model_library_state)"
  estimate="$(sed -n 's/^DOWNLOAD_ESTIMATE_BYTES=//p' "$RUNTIME_ROOT/rocm-torch/runtime.conf" | head -1)"
  available="$(df -B1 --output=avail "$(filesystem_probe_path "$(media_data_dir)")" | tail -1 | tr -d ' ')"
  "$PYTHON_BIN" - "$ENV_STATUS_FILE" "$core_state" "$runtime_state" "$gpu_state" "$model_state" "$available" "$estimate" "$runtime_detail" "$gpu_detail" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
core, runtime, gpu, model, available, estimate, runtime_detail, gpu_detail = sys.argv[2:]
missing = core != "current" or runtime != "current" or gpu != "ok" or model != "ok"
def item(identifier, label, state, message=None, detail=None):
    value = {"id": identifier, "label": label, "state": state}
    if message:
        value["message"] = message
        value["action"] = {"kind": "open_route", "route": "/x/media-forge/workspace/settings"}
    if detail:
        value["detail"] = detail
    return value
runtime_state = {"current": "ok", "in_progress": "in_progress", "error": "error"}.get(runtime, "missing")
runtime_message = runtime_detail or (None if runtime_state == "ok" else f"Run ./mf.sh env build rocm-torch; estimated download {int(estimate)} bytes")
gpu_state = "ok" if gpu == "ok" else ("error" if gpu == "error" else "checking")
gpu_message = gpu_detail or (None if gpu_state == "ok" else "GPU verification has not completed")
setup = [
    item("core_env", "Core environment", "ok" if core == "current" else "missing", None if core == "current" else "Run ./mf.sh serve"),
    item("rocm_runtime", "Image worker environment", runtime_state, runtime_message),
    item("gpu", "GPU verification", gpu_state, gpu_message),
    item("model_library", "Model library", "ok" if model == "ok" else "missing", None if model == "ok" else "Configure an NVMe model library"),
    item("disk", "Free disk space", "ok", detail=f"{int(available)} bytes available"),
]
path.parent.mkdir(parents=True, exist_ok=True)
temporary = path.with_suffix(".tmp")
temporary.write_text(json.dumps({"status": "setup_required" if missing else "healthy", "setup": setup}, indent=2) + "\n", encoding="utf-8")
temporary.replace(path)
PY
}

doctor() {
  export_cache_paths no
  local core runtime model config_path available
  core="$(stamp_state "$VENV" "$REPO_ROOT/requirements.txt")"
  runtime="$(stamp_state "$RUNTIME_ROOT/rocm-torch/.venv" "$RUNTIME_ROOT/rocm-torch/requirements.txt")"
  model="$(model_library_state)"
  config_path="$(control_deck_config || true)"
  available="$(df -B1 --output=avail "$(filesystem_probe_path "$(media_data_dir)")" | tail -1 | tr -d ' ')"
  printf 'core_env=%s\n' "$core"
  printf 'rocm_runtime=%s\n' "$runtime"
  printf 'gpu_tool_rocm_smi=%s\n' "$(command -v rocm-smi || printf missing)"
  printf 'gpu_tool_rocminfo=%s\n' "$(command -v rocminfo || printf missing)"
  printf 'model_library=%s\n' "$model"
  printf 'blender_runtime=%s\n' "$(blender_runtime_state)"
  printf 'media_data_dir=%s\n' "$(media_data_dir)"
  printf 'model_store_root=%s\n' "$(model_store_root)"
  printf 'control_deck_config=%s\n' "${config_path:-unavailable}"
  printf 'PIP_CACHE_DIR=%s\n' "$PIP_CACHE_DIR"
  printf 'UV_CACHE_DIR=%s\n' "$UV_CACHE_DIR"
  printf 'HF_HOME=%s\n' "$HF_HOME"
  printf 'HF_ENABLE_PARALLEL_LOADING=%s\n' "$HF_ENABLE_PARALLEL_LOADING"
  printf 'AMD_COMGR_CACHE=%s\n' "$AMD_COMGR_CACHE"
  printf 'AMD_COMGR_CACHE_DIR=%s\n' "$AMD_COMGR_CACHE_DIR"
  printf 'MIOPEN_CUSTOM_CACHE_DIR=%s\n' "$MIOPEN_CUSTOM_CACHE_DIR"
  printf 'MIOPEN_USER_DB_PATH=%s\n' "$MIOPEN_USER_DB_PATH"
  printf 'disk_available_bytes=%s\n' "$available"
}

gpu_verify() {
  local python="$RUNTIME_ROOT/rocm-torch/.venv/bin/python"
  local snapshot temporary
  snapshot="$RUNTIME_ROOT/rocm-torch/.gpu-check.json"
  temporary="$snapshot.tmp"
  "$python" - "$temporary" <<'PY'
import json
import sys
import time
from pathlib import Path
import torch

started = time.perf_counter()
if not torch.cuda.is_available():
    raise SystemExit("torch.cuda.is_available() is false")
devices = []
for index in range(torch.cuda.device_count()):
    props = torch.cuda.get_device_properties(index)
    devices.append({
        "index": index,
        "name": torch.cuda.get_device_name(index),
        "gcn_arch": getattr(props, "gcnArchName", "unknown"),
        "total_memory_bytes": int(props.total_memory),
    })
torch.cuda.set_device(0)
left = torch.arange(4096, device="cuda", dtype=torch.float32)
result = float((left * 2).sum().item())
expected = float((torch.arange(4096, dtype=torch.float32) * 2).sum().item())
if result != expected:
    raise SystemExit(f"GPU tensor result mismatch: {result} != {expected}")
free_bytes, total_bytes = torch.cuda.mem_get_info(0)
payload = {
    "torch_version": torch.__version__,
    "hip_version": torch.version.hip,
    "device_count": torch.cuda.device_count(),
    "devices": devices,
    "selected_device": 0,
    "free_memory_bytes": int(free_bytes),
    "total_memory_bytes": int(total_bytes),
    "tensor_result": result,
    "elapsed_sec": time.perf_counter() - started,
}
path = Path(sys.argv[1])
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2))
PY
  mv -- "$temporary" "$snapshot"
}

model_registry_manifest() {
  printf '%s/worker_packs/image/models.json\n' "$REPO_ROOT"
}

model_catalog_manifest() {
  printf '%s/worker_packs/image/catalog.json\n' "$REPO_ROOT"
}

list_models() {
  ensure_env "$VENV" "$REPO_ROOT/requirements.txt" "core"
  PYTHONPATH="$REPO_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}" "$VENV/bin/python" - \
    "$(model_registry_manifest)" "$(model_catalog_manifest)" "$HF_HOME" "$(model_store_root)" <<'PY'
import sys
from pathlib import Path

from mediaforge.models import ModelRegistry

for model in ModelRegistry.load(
    Path(sys.argv[1]), catalog_manifest=Path(sys.argv[2]), hf_home=Path(sys.argv[3]),
    model_store_root=Path(sys.argv[4]),
).all():
    print(
        f"{model.model_id}\tname={model.display_name}\tdomains={','.join(model.domains)}"
        f"\townership={model.ownership}\tremovable={'yes' if model.removable else 'no'}"
        f"\tstate={model.state}\tinstalled={'yes' if model.installed else 'no'}"
        f"\thealthy={'yes' if model.healthy else 'no'}\trevision={model.revision}"
    )
PY
}

download_model() {
  local name="$1" accept_license="${2:-no}" model_id
  case "$name" in
    flux2-klein-4b) model_id=black-forest-labs/FLUX.2-klein-4B ;;
    minimax-h3-gguf) model_id=unsloth/MiniMax-H3-GGUF ;;
    *) die "unknown model: $name" ;;
  esac
  run_model_operation install "$model_id" "$accept_license"
  list_models
}

remove_model() {
  local name="$1" model_id
  case "$name" in
    flux2-klein-4b) model_id=black-forest-labs/FLUX.2-klein-4B ;;
    wan2.2-ti2v-5b) model_id=Wan-AI/Wan2.2-TI2V-5B ;;
    wan2.2-i2v-a14b) model_id=Wan-AI/Wan2.2-I2V-A14B ;;
    wan2.2-t2v-a14b) model_id=Wan-AI/Wan2.2-T2V-A14B ;;
    *) die "unknown model: $name" ;;
  esac
  run_model_operation remove "$model_id"
  list_models
}

run_model_operation() {
  local action="$1" model_id="$2" accept_license="${3:-no}"
  ensure_env "$VENV" "$REPO_ROOT/requirements.txt" "core"
  PYTHONPATH="$REPO_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}" "$VENV/bin/python" - \
    "$(media_data_dir)" "$(model_registry_manifest)" "$(model_catalog_manifest)" \
    "$(model_store_root)" "$HF_HOME" "$action" "$model_id" "$accept_license" <<'PY'
import asyncio
import sys
from pathlib import Path

from mediaforge.model_manager import ModelOperationManager
from mediaforge.models import ModelOperationError, TERMINAL_MODEL_OPERATION_STATES
from mediaforge.store import Store


async def main() -> int:
    data_dir, manifest, catalog, managed, external = map(Path, sys.argv[1:6])
    action, model_id, accept_license = sys.argv[6:9]
    store = Store(data_dir)
    store.initialize()
    service = ModelOperationManager(
        store,
        model_manifest=manifest,
        catalog_manifest=catalog,
        model_store_root=managed,
        hf_home=external,
    )
    await service.start()
    try:
        if action == "install":
            model = next(
                (item for item in service.catalog()["items"] if item["model_id"] == model_id),
                None,
            )
            acceptance = model["license_acceptance_id"] if model is not None and accept_license == "yes" else None
            operation = service.install(model_id, license_acceptance=acceptance)
        else:
            operation = service.remove(model_id)
    except ModelOperationError as exc:
        await service.stop()
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 1
    last = None
    while True:
        current = store.get_model_operation(operation.id)
        observed = (current.state, current.bytes_done, current.error_code)
        if observed != last:
            print(
                f"operation={current.id} state={current.state} "
                f"bytes={current.bytes_done}/{current.bytes_total} error={current.error_code or '-'}",
                flush=True,
            )
            last = observed
        if current.state in TERMINAL_MODEL_OPERATION_STATES:
            await service.stop()
            return 0 if current.state.value == "ready" else 1
        await asyncio.sleep(0.5)


try:
    raise SystemExit(asyncio.run(main()))
except KeyboardInterrupt:
    print("model operation interrupted; partial download remains resumable", file=sys.stderr)
    raise SystemExit(130)
PY
}

build_runtime() {
  local name="$1" root requirements description estimate required available before_cache after_cache started elapsed size
  root="$RUNTIME_ROOT/$name"
  requirements="$root/requirements.txt"
  [ -d "$root" ] || die "unknown runtime: $name"
  [ -f "$root/runtime.conf" ] || die "runtime metadata is missing: $name"
  # shellcheck disable=SC1090
  source "$root/runtime.conf"
  description="$DESCRIPTION"
  estimate="$DOWNLOAD_ESTIMATE_BYTES"
  required="$REQUIRED_FREE_BYTES"
  available="$(df -B1 --output=avail "$root" | tail -1 | tr -d ' ')"
  info "runtime: $description"
  info "estimated download: $estimate bytes"
  info "disk check: $available bytes available; $required bytes required"
  if [ "$available" -lt "$required" ]; then
    write_environment_status error checking "Insufficient disk space: $available bytes available; $required bytes required"
    die "insufficient disk space; runtime build was not started"
  fi
  before_cache="$(directory_bytes "$PIP_CACHE_DIR")"
  started="$(date +%s)"
  write_environment_status in_progress checking "Installing $description; estimated download $estimate bytes"
  if ! ensure_env "$root/.venv" "$requirements" "$name runtime" verbose; then
    write_environment_status error checking "Runtime dependency installation failed"
    die "failed to build $name runtime"
  fi
  write_environment_status current checking
  if ! gpu_verify; then
    write_environment_status current error "" "ROCm GPU verification failed; inspect mf.sh env build output"
    die "ROCm GPU verification failed"
  fi
  elapsed="$(( $(date +%s) - started ))"
  after_cache="$(directory_bytes "$PIP_CACHE_DIR")"
  size="$(directory_bytes "$root/.venv")"
  write_environment_status
  info "runtime build elapsed: $elapsed seconds"
  info "runtime disk usage: $size bytes"
  info "pip cache delta: $((after_cache - before_cache)) bytes"
}

start_auto_provision() {
  local runtime_state
  runtime_state="$(stamp_state "$RUNTIME_ROOT/rocm-torch/.venv" "$RUNTIME_ROOT/rocm-torch/requirements.txt")"
  [ "$runtime_state" != current ] || return 0
  if ! auto_provision_enabled; then
    info "rocm-torch runtime setup is required; auto_provision is disabled"
    return 0
  fi
  command -v flock >/dev/null || die "flock is required for automatic runtime provisioning"
  info "starting visible rocm-torch runtime provisioning in the background"
  (
    exec 9>"$RUNTIME_ROOT/rocm-torch/.build.lock"
    if ! flock -n 9; then
      info "rocm-torch runtime provisioning is already running"
      exit 0
    fi
    build_runtime rocm-torch
  ) &
}

list_envs() {
  printf 'core\tstate=%s\tsize_bytes=%s\trefs=-\n' \
    "$(stamp_state "$VENV" "$REPO_ROOT/requirements.txt")" "$(directory_bytes "$VENV")"
  local root refs
  for root in "$RUNTIME_ROOT"/*; do
    [ -d "$root" ] || continue
    refs="$(awk 'NF && $1 !~ /^#/' "$root/.refs" 2>/dev/null | paste -sd, -)"
    if [ "$(basename "$root")" = "blender-4.5.9" ]; then
      printf 'blender-4.5.9\tstate=%s\tsize_bytes=%s\trefs=%s\n' \
        "$(blender_runtime_state)" "$(directory_bytes "$root")" "${refs:--}"
      continue
    fi
    printf '%s\tstate=%s\tsize_bytes=%s\trefs=%s\n' \
      "$(basename "$root")" "$(stamp_state "$root/.venv" "$root/requirements.txt")" \
      "$(directory_bytes "$root/.venv")" "${refs:--}"
  done
}

prune_envs() {
  local root refs answer size
  for root in "$RUNTIME_ROOT"/*; do
    [ -d "$root" ] || continue
    [ -d "$root/.venv" ] || continue
    refs="$(awk 'NF && $1 !~ /^#/' "$root/.refs" 2>/dev/null || true)"
    if [ -n "$refs" ]; then
      info "keeping $(basename "$root"): referenced by $(printf '%s' "$refs" | paste -sd, -)"
      continue
    fi
    size="$(directory_bytes "$root/.venv")"
    printf 'prune %s (%s bytes)? [y/N] ' "$(basename "$root")" "$size"
    read -r answer
    if [ "$answer" = y ] || [ "$answer" = Y ]; then
      safe_remove_venv "$root/.venv"
      info "removed $(basename "$root") runtime environment"
    else
      info "kept $(basename "$root")"
    fi
  done
}

blender_runtime() {
  local action="$1"
  "$PYTHON_BIN" "$REPO_ROOT/scripts/blender_runtime.py" "$action" \
    --manifest "$REPO_ROOT/config/blender-runtime.json" \
    --runtime-root "$RUNTIME_ROOT/blender-4.5.9"
}

blender_runtime_state() {
  blender_runtime status >/dev/null 2>&1 && printf 'ready' || printf 'missing'
}

blender_manager() {
  local port="${MEDIA_FORGE_PORT:-9130}"
  "$PYTHON_BIN" "$REPO_ROOT/scripts/blender_manager_cli.py" \
    --base-url "http://127.0.0.1:$port" "$@"
}

serve() {
  ensure_env "$VENV" "$REPO_ROOT/requirements.txt" "core"
  write_environment_status
  start_auto_provision
  export MEDIA_FORGE_ENV_STATUS_FILE="$ENV_STATUS_FILE"
  export MEDIA_FORGE_DATA_DIR="${MEDIA_FORGE_DATA_DIR:-$(media_data_dir)}"
  export MEDIA_FORGE_MODEL_STORE_ROOT="${MEDIA_FORGE_MODEL_STORE_ROOT:-$(model_store_root)}"
  export PYTHONPATH="$REPO_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
  exec "$VENV/bin/python" -m uvicorn mediaforge.app:app --host 127.0.0.1 --port "${MEDIA_FORGE_PORT:-9130}"
}

usage() {
  cat <<'EOF'
Usage:
  ./mf.sh serve
  ./mf.sh doctor
  ./mf.sh env build <name>
  ./mf.sh env list
  ./mf.sh env prune
  ./mf.sh blender build
  ./mf.sh blender status
  ./mf.sh blender managed-status
  ./mf.sh blender install
  ./mf.sh blender web-install
  ./mf.sh blender update
  ./mf.sh blender switch <runtime-id>
  ./mf.sh blender repair <runtime-id>
  ./mf.sh blender remove-preview <runtime-id>
  ./mf.sh blender remove <runtime-id> [--yes]
  ./mf.sh model list
  ./mf.sh model download flux2-klein-4b
  ./mf.sh model download minimax-h3-gguf --accept-license
  ./mf.sh model remove flux2-klein-4b
  ./mf.sh bundle build <version> <output-dir>
  ./mf.sh test
EOF
}

main() {
  check_root
  check_python
  case "${1:-serve}" in
    serve) [ "$#" -eq 1 ] || die "serve takes no arguments"; export_cache_paths yes; serve ;;
    doctor) [ "$#" -eq 1 ] || die "doctor takes no arguments"; export_cache_paths no; doctor ;;
    test) [ "$#" -eq 1 ] || die "test takes no arguments"; export_cache_paths yes; ensure_env "$VENV" "$REPO_ROOT/requirements.txt" "core"; "$VENV/bin/python" -m pytest ;;
    env)
      export_cache_paths yes
      case "${2:-}" in
        build) [ "$#" -eq 3 ] || die "env build requires one runtime name"; build_runtime "$3" ;;
        list) [ "$#" -eq 2 ] || die "env list takes no arguments"; list_envs ;;
        prune) [ "$#" -eq 2 ] || die "env prune takes no arguments"; prune_envs ;;
        *) usage; exit 2 ;;
      esac
      ;;
    blender)
      case "${2:-}" in
        build|status) [ "$#" -eq 2 ] || die "blender ${2:-action} takes no arguments"; blender_runtime "$2" ;;
        managed-status) [ "$#" -eq 2 ] || die "blender managed-status takes no arguments"; blender_manager status ;;
        install|web-install|update) [ "$#" -eq 2 ] || die "blender ${2:-action} takes no arguments"; blender_manager "$2" ;;
        switch|repair|remove-preview) [ "$#" -eq 3 ] || die "blender ${2:-action} requires one runtime ID"; blender_manager "$2" "$3" ;;
        remove)
          [ "$#" -eq 3 ] || { [ "$#" -eq 4 ] && [ "$4" = "--yes" ]; } || \
            die "blender remove requires one runtime ID and optional --yes"
          if [ "$#" -eq 4 ]; then
            blender_manager remove "$3" "$4"
          else
            blender_manager remove "$3"
          fi
          ;;
        *) usage; exit 2 ;;
      esac
      ;;
    model)
      export_cache_paths yes
      case "${2:-}" in
        list) [ "$#" -eq 2 ] || die "model list takes no arguments"; list_models ;;
        download)
          [ "$#" -eq 3 ] || { [ "$#" -eq 4 ] && [ "$4" = "--accept-license" ]; } || \
            die "model download requires a model name and optional --accept-license"
          download_model "$3" "$([ "${4:-}" = "--accept-license" ] && printf yes || printf no)"
          ;;
        remove) [ "$#" -eq 3 ] || die "model remove requires one model name"; remove_model "$3" ;;
        *) usage; exit 2 ;;
      esac
      ;;
    bundle)
      case "${2:-}" in
        build)
          [ "$#" -eq 4 ] || die "bundle build requires version and output directory"
          bundle_build_root="$RUNTIME_ROOT/bundle-build"
          ensure_env "$bundle_build_root/.venv" "$bundle_build_root/requirements.txt" "bundle build"
          "$bundle_build_root/.venv/bin/python" "$REPO_ROOT/scripts/build_release_bundle.py" \
            --version "$3" --output-dir "$4" \
            --pyinstaller "$bundle_build_root/.venv/bin/pyinstaller"
          ;;
        *) usage; exit 2 ;;
      esac
      ;;
    *) usage; exit 2 ;;
  esac
}

main "$@"
