"""Dedicated pathname-socket canary, NOT a production sandbox or installer.

Run without sudo. The administrator must separately load the adjacent diagnostic
profile. --baseline deliberately omits that profile and must never pass acceptance.
Only task-created sockets are contacted; temporary files stay in ControlDeck data.
"""
from __future__ import annotations

import argparse
import errno
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
from typing import Any


PROFILE = "mediaforge-ipc-canary-v1"
PROBE_ROOT = Path("/data1tb/ControlDeck/data/feature-data/media-forge/ipc-probes")
PAYLOAD = b"mf-owned-canary"
CHILD = r'''
import json, socket, sys
result = {}
try:
    with open('/proc/self/attr/current') as stream:
        result['profile'] = stream.read().strip()
except OSError as error:
    result['profile_error'] = error.errno
for name, path in zip(('allowed', 'outside'), sys.argv[1:]):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
        peer.settimeout(1)
        try:
            peer.connect(path)
            peer.sendall(b'mf-owned-canary')
            result[name] = {'connected': True}
        except OSError as error:
            result[name] = {'connected': False, 'errno': error.errno}
print(json.dumps(result))
'''


def accepted(observation: dict[str, Any]) -> bool:
    """Missing evidence, unrelated errors and unconfined baselines are failures."""
    child = observation.get("child", {})
    return (
        observation.get("mode") == "profile"
        and observation.get("returncode") == 0
        and child.get("profile") == f"{PROFILE} (enforce)"
        and child.get("allowed") == {"connected": True}
        and child.get("outside", {}).get("connected") is False
        and child.get("outside", {}).get("errno") in (errno.EACCES, errno.EPERM)
        and observation.get("received") == {"allowed": PAYLOAD.decode(), "outside": None}
    )


def observe(root: Path, *, baseline: bool) -> dict[str, Any]:
    """Own both peers and reap the single, bounded diagnostic child."""
    result: dict[str, Any] = {"mode": "baseline" if baseline else "profile"}
    with tempfile.TemporaryDirectory(dir=root, prefix="") as directory:
        peers: dict[str, socket.socket] = {}
        try:
            paths = [str(Path(directory) / name) for name in ("ok.sock", "outside.sock")]
            for name, path in zip(("allowed", "outside"), paths):
                peer = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                peers[name] = peer
                peer.settimeout(0.2)
                peer.bind(path)
                peer.listen(1)
            command = ["/usr/bin/python3", "-I", "-S", "-c", CHILD, *paths]
            if not baseline:
                command = ["/usr/bin/aa-exec", "-p", PROFILE, "--", *command]
            try:
                completed = subprocess.run(
                    command, stdin=subprocess.DEVNULL, capture_output=True,
                    timeout=5, close_fds=True, check=False,
                    env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
                )
                result["returncode"] = completed.returncode
                result["stderr"] = completed.stderr.decode(errors="replace")[:2048]
                try:
                    child = json.loads(completed.stdout)
                    if not isinstance(child, dict):
                        raise ValueError("non-object child result")
                    result["child"] = child
                except (ValueError, UnicodeError):
                    result["error"] = "missing_or_invalid_child_evidence"
            except subprocess.TimeoutExpired:
                result["error"] = "probe_timeout"
            except OSError as error:
                result["error"] = "probe_launch_failed"
                result["errno"] = error.errno
            received: dict[str, str | None] = {}
            for name, peer in peers.items():
                try:
                    connection, _ = peer.accept()
                except TimeoutError:
                    received[name] = None
                else:
                    with connection:
                        connection.settimeout(1)
                        received[name] = connection.recv(64).decode(errors="replace")
            result["received"] = received
        finally:
            for peer in peers.values():
                peer.close()
    result["passed"] = accepted(result)
    result["temporary_peers_removed"] = not Path(directory).exists()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("run as the MediaForge service user, never as root")
    # Validate the fixed ancestor before creating only our diagnostic directory.
    parent = PROBE_ROOT.parent.resolve(strict=True)
    if parent != PROBE_ROOT.parent or PROBE_ROOT.is_symlink():
        parser.error("diagnostic root must not traverse a symlink")
    PROBE_ROOT.mkdir(mode=0o700, exist_ok=True)
    info = PROBE_ROOT.stat()
    if info.st_uid != os.geteuid() or info.st_mode & 0o077:
        parser.error("diagnostic directory must be owned by this user with mode 0700")
    result = observe(PROBE_ROOT, baseline=args.baseline)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
