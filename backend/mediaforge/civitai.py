"""Search and resolve models distributed by Civitai.

Civitai does not distribute diffusers repositories. One model version is one
``.safetensors`` file, and the file does not say which family it belongs to.
The site does say, as ``baseModel`` on the version, and that statement is what
Media Forge records and later hands to the single-file adapter.

Measured against the live API (2026-08-25):

* ``GET /api/v1/models`` needs no authorization
* a version's file carries ``sizeKB``, ``hashes.SHA256`` and ``downloadUrl``
* the download URL answers with a redirect to a signed URL — but only for a
  browser-shaped ``User-Agent``. The default one from an HTTP client is
  refused with 403, which looks like an authorization problem and is not.

Only Checkpoints are searched. Civitai is mostly LoRAs, and Media Forge has no
LoRA path yet: listing them would fill the results with things that install and
then cannot be used.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

CIVITAI_ORIGIN = "https://civitai.com"
# 既定の UA は 403 で弾かれる。認証の問題ではないので、鍵を求めない。
USER_AGENT = "MediaForge/1.0 (+https://github.com/souten-yd/ControlDeckMediaForge)"
SEARCH_LIMIT = 30
MAX_METADATA_BYTES = 4_000_000

# Civitai の sort 名。Media Forge 側の並び順から引く。
SORTS = {
    "downloads": "Most Downloaded",
    "likes": "Most Liked",
    "lastModified": "Newest",
    "createdAt": "Newest",
}


class CivitaiError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CivitaiFile:
    name: str
    size_bytes: int
    sha256: str
    download_url: str


@dataclass(frozen=True)
class CivitaiVersion:
    model_id: int
    version_id: int
    name: str
    base_model: str
    file: CivitaiFile


def repo_id_for(model_id: int) -> str:
    """Media Forge 内での識別子。

    Civitai は数字の id しか持たないので、名前は使わない。名前は作者が後から
    変えられるが、id は変わらない。来歴として意味を持つのは id の方である。
    """
    return f"civitai/{int(model_id)}"


def _client(transport: httpx.AsyncBaseTransport | None, timeout_sec: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=transport,
        timeout=timeout_sec,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )


def _checkpoint_file(files: Any) -> CivitaiFile | None:
    """その version の本体。VAE や設定ファイルは本体ではない。"""
    if not isinstance(files, list):
        return None
    for item in files:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        if str(item.get("type") or "") != "Model":
            continue
        if str(metadata.get("format") or "") != "SafeTensor":
            # pickle は読み込みが任意のコードを実行しうる。取り込まない。
            continue
        digest = str((item.get("hashes") or {}).get("SHA256") or "").lower()
        size_kb = item.get("sizeKB")
        url = str(item.get("downloadUrl") or "")
        if len(digest) != 64 or not isinstance(size_kb, (int, float)) or size_kb <= 0 or not url:
            continue
        return CivitaiFile(
            name=str(item.get("name") or "model.safetensors"),
            size_bytes=int(size_kb * 1024),
            sha256=digest,
            download_url=url,
        )
    return None


def _payload(response: httpx.Response) -> dict[str, Any]:
    if response.status_code in (401, 403):
        raise CivitaiError(
            "custom_model_access_denied",
            "この配布物は Civitai の許可が要ります。配布元で条件を確認してください",
        )
    if response.status_code == 404:
        raise CivitaiError("custom_model_not_found", "その model は見つかりませんでした")
    if response.status_code != 200:
        raise CivitaiError("custom_model_source_unreachable", "配布元に接続できませんでした")
    if len(response.content) > MAX_METADATA_BYTES:
        raise CivitaiError("custom_model_metadata_too_large", "モデル情報が大きすぎます")
    try:
        document = response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise CivitaiError("custom_model_metadata_invalid", "応答を読み取れませんでした") from exc
    if not isinstance(document, dict):
        raise CivitaiError("custom_model_metadata_invalid", "応答を読み取れませんでした")
    return document


class CivitaiSource:
    """One distribution site, behind the same two calls as the other one."""

    kind = "civitai"

    def __init__(
        self,
        *,
        origin: str = CIVITAI_ORIGIN,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_sec: float = 20.0,
    ):
        self.origin = origin.rstrip("/")
        self.transport = transport
        self.timeout_sec = timeout_sec

    async def search(
        self, query: str, *, sort: str = "downloads", limit: int = SEARCH_LIMIT
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            # LoRA は取り込めても使えない。並べない。
            "types": "Checkpoint",
            "sort": SORTS.get(sort, "Most Downloaded"),
            "limit": max(1, min(SEARCH_LIMIT, limit)),
            "nsfw": "false",
        }
        if query.strip():
            params["query"] = query.strip()
        try:
            async with _client(self.transport, self.timeout_sec) as client:
                response = await client.get(f"{self.origin}/api/v1/models", params=params)
        except httpx.HTTPError as exc:
            raise CivitaiError(
                "custom_model_source_unreachable", "配布元を検索できませんでした"
            ) from exc
        items = _payload(response).get("items")
        if not isinstance(items, list):
            raise CivitaiError("custom_model_metadata_invalid", "検索結果を読み取れませんでした")

        found: list[dict[str, Any]] = []
        for item in items[:SEARCH_LIMIT]:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id")
            if not isinstance(model_id, int) or isinstance(model_id, bool) or model_id <= 0:
                continue
            versions = item.get("modelVersions")
            version = versions[0] if isinstance(versions, list) and versions else {}
            if not isinstance(version, dict):
                continue
            checkpoint = _checkpoint_file(version.get("files"))
            if checkpoint is None:
                # SafeTensor の本体が無いものは取り込めない。並べても押せない。
                continue
            statistics = item.get("stats") if isinstance(item.get("stats"), dict) else {}
            tags = item.get("tags") if isinstance(item.get("tags"), list) else []
            found.append({
                "repo_id": repo_id_for(model_id),
                "display_name": str(item.get("name") or "")[:120],
                "author": str((item.get("creator") or {}).get("username") or ""),
                "downloads": int(statistics.get("downloadCount") or 0),
                "likes": int(statistics.get("thumbsUpCount") or 0),
                "last_modified": str(version.get("publishedAt") or ""),
                "pipeline_tag": "text-to-image",
                "library_name": "single-file",
                "gated": bool(item.get("nsfw")),
                "license": "配布元の表記に従う",
                "tags": [str(tag) for tag in tags[:24] if isinstance(tag, str)],
                "weight_bytes": checkpoint.size_bytes,
                "weight_precision": str(
                    ((version.get("files") or [{}])[0].get("metadata") or {}).get("fp") or ""
                ),
                # 取り込むときに要る。version を選び直させないための控え。
                "revision": str(version.get("id") or ""),
                "base_model": str(version.get("baseModel") or ""),
            })
        return found

    async def version(self, model_id: int, version_id: int | None = None) -> CivitaiVersion:
        """Resolve one version, or the newest one when none is named."""
        try:
            async with _client(self.transport, self.timeout_sec) as client:
                if version_id is not None:
                    document = _payload(
                        await client.get(f"{self.origin}/api/v1/model-versions/{int(version_id)}")
                    )
                else:
                    model = _payload(await client.get(f"{self.origin}/api/v1/models/{int(model_id)}"))
                    versions = model.get("modelVersions")
                    if not isinstance(versions, list) or not versions:
                        raise CivitaiError("custom_model_not_found", "取り込める版がありません")
                    document = versions[0] if isinstance(versions[0], dict) else {}
        except httpx.HTTPError as exc:
            raise CivitaiError(
                "custom_model_source_unreachable", "モデル情報を取得できませんでした"
            ) from exc
        checkpoint = _checkpoint_file(document.get("files"))
        if checkpoint is None:
            raise CivitaiError(
                "custom_model_digest_missing",
                "SafeTensor 形式の本体と digest が配布元にありません。検証できないものは取り込めません",
            )
        base_model = str(document.get("baseModel") or "")
        if not base_model:
            raise CivitaiError(
                "custom_model_family_unknown",
                "配布元がこの checkpoint の系統を示していません。どの pipeline で読むか決められません",
            )
        resolved_id = document.get("id")
        return CivitaiVersion(
            model_id=int(model_id),
            version_id=int(resolved_id) if isinstance(resolved_id, int) else int(version_id or 0),
            name=str(document.get("name") or "")[:120],
            base_model=base_model,
            file=checkpoint,
        )
