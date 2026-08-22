from __future__ import annotations

from collections.abc import Mapping

from fastapi import HTTPException, Request

from .client import ControlDeckHostClient, HostApiError, HostIdentity


async def require_host_service_headers(
    headers: Mapping[str, str], host: ControlDeckHostClient,
) -> HostIdentity:
    try:
        return await host.authenticate(headers)
    except HostApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code}) from exc


async def require_host_service(request: Request, host: ControlDeckHostClient) -> HostIdentity:
    return await require_host_service_headers(request.headers, host)


# base64 のアルファベットには "/" が含まれるため、チャンクの先頭が "/" になると
# 約 64 分の 1 の確率でパスとして誤検出される。実際に端末からの画像取り込みが
# 途中で失敗していた。運搬用のバイナリ本体は検査対象から外す。
BINARY_FIELDS = frozenset({"base64"})
# path は短い。長い文字列を検査してもコストが増えるだけで守れるものは増えない。
MAX_INSPECTED_LENGTH = 4096


def reject_host_paths(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in BINARY_FIELDS:
                continue
            reject_host_paths(nested)
    elif isinstance(value, list):
        for nested in value:
            reject_host_paths(nested)
    elif isinstance(value, str) and len(value) <= MAX_INSPECTED_LENGTH:
        if value.startswith(("/", "~/", "file:")) or (len(value) >= 3 and value[1] == ":" and value[2] in "\\/"):
            raise HTTPException(status_code=422, detail={"code": "unscoped_host_path"})
