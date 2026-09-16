"""Host-venv diagnostic for scoped AI cancellation/deadline and lease return.

Fresh dedicated mf-e2e credentials only. Provider /slots is read-only observation;
all inference uses the Add-on Runtime gateway. No asset/project/model changes.
The short-lived diagnostic login is revoked in finally, without printing secrets.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
import time


def main() -> None:
    import httpx
    from app.addons import tokens
    from app.database import SessionLocal
    from app.models import User
    from app.security.sessions import SESSION_COOKIE, create_session, revoke_session

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from mediaforge.host.ai import HostAIGateway, HostAIError
    from mediaforge.host.client import ControlDeckHostClient

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("cancel", "deadline"), required=True)
    args = parser.parse_args()
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        user_id = user.id
        login = create_session(db, user, "127.0.0.1", "MediaForge scoped AI cancellation acceptance")

    async def run() -> None:
        host = ControlDeckHostClient("http://127.0.0.1:8765")
        try:
            identity = await host.authenticate(headers)
            async with httpx.AsyncClient(timeout=5) as observer:
                async def observe() -> tuple[bool, dict]:
                    slots = await observer.get("http://127.0.0.1:8097/slots")
                    slots.raise_for_status()
                    snapshot = await observer.get("http://127.0.0.1:8765/api/v1/resources",
                                                  headers={"Cookie": f"{SESSION_COOKIE}={login}"})
                    snapshot.raise_for_status()
                    return (any(slot.get("is_processing") for slot in slots.json()),
                            {lease["lease_id"]: lease for lease in snapshot.json()["leases"]})

                busy, baseline = await observe()
                assert not busy, "Do not interfere with an existing inference"
                task = asyncio.create_task(HostAIGateway(host).complete_streamed(
                    identity, "text.generate", [{"role": "user", "content":
                        "For a bounded cancellation diagnostic, output integers 1 through 4000 "
                        "in order in a JSON array. Output only the array."}],
                    response_format={"type": "json_object"}, max_tokens=8192,
                    timeout_seconds=1 if args.mode == "deadline" else 30, max_output_bytes=65536,
                ))
                started = time.monotonic()
                try:
                    while time.monotonic() - started < 15:
                        busy, current = await observe()
                        own = {key: value for key, value in current.items() if key not in baseline}
                        if busy and len(own) == 1 and next(iter(own.values()))["state"] == "active":
                            break
                        assert not task.done(), "Inference ended before live cancellation observation"
                        await asyncio.sleep(.2)
                    else:
                        raise RuntimeError("No unique live inference/lease observed")
                    lease_id = next(iter(own))
                    print(json.dumps({"mode": args.mode, "observed_active_lease": lease_id}), flush=True)
                    if args.mode == "cancel":
                        task.cancel()
                        result = (await asyncio.gather(task, return_exceptions=True))[0]
                        assert isinstance(result, asyncio.CancelledError)
                    else:
                        result = (await asyncio.gather(task, return_exceptions=True))[0]
                        assert isinstance(result, HostAIError), "Deadline must not return partial success"
                        assert result.code == "host_ai_unavailable"
                    terminal = time.monotonic()
                    for _ in range(20):
                        busy, current = await observe()
                        state = current.get(lease_id, {}).get("state")
                        if not busy and state == "released":
                            print(json.dumps({"mode": args.mode, "lease_id": lease_id,
                                "lease_state": state, "inference_busy": busy,
                                "total_seconds": round(time.monotonic() - started, 3),
                                "after_local_terminal_seconds": round(time.monotonic() - terminal, 3)}), flush=True)
                            return
                        await asyncio.sleep(.25)
                    raise RuntimeError("Inference/lease did not terminate within five seconds")
                finally:
                    if not task.done():
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
        finally:
            await host.close()

    try:
        # Issuer/ORM are synchronous diagnostic setup, outside the async path.
        headers = {
            "Authorization": "Bearer " + tokens.issue("media-forge", subject=f"user:{user_id}",
                kind="service", actor_user_id=user_id, grant_ids=[]),
            "X-Control-Deck-Addon-ID": "media-forge",
        }
        asyncio.run(run())
    finally:
        with SessionLocal() as db:
            revoke_session(db, login)


if __name__ == "__main__":
    main()
