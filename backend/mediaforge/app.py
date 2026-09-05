from __future__ import annotations

import asyncio
import base64
import hashlib
import inspect
import logging
from io import BytesIO
import json
import os
import shutil
import sys
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError, __version__ as PILLOW_VERSION
from pydantic import BaseModel, ConfigDict, ValidationError

from . import __version__, library, preferences, thumbnails
from .asset_import import (
    MAX_IMPORT_BYTES,
    MAX_VIDEO_IMPORT_BYTES,
    VIDEO_MEDIA_TYPES,
    AssetImportError,
    import_asset_bytes,
    import_image_asset,
)
from .asset_placement import (
    PlacementItem,
    PlacementManifest,
    PlacementPlanError,
    PlacementReceipt,
    ProjectAssetPlacement,
    placement_filename,
    plan_placements,
)
from .asset_brief import (
    AssetBriefError,
    infer_brief_from_intent,
    parse_brief,
    resolve_layout,
)
from .blender_runtime import BlenderRuntimeRegistryError, BlenderRuntimeResolver
from .blender_manager import BlenderRuntimeManager
from .blender_operation import BlenderRuntimeOperationError
from .blender_session_manager import BlenderSessionError, BlenderSessionManager
from .blender_rfb import relay_rfb
from .blender_web import BlenderWebPack, BlenderWebPackError
from .config import Settings
from .custom_models import DEFAULT_MODEL_SOURCE, MODEL_SOURCES, CustomModelCatalog, CustomModelError
from .composer import (
    CreativeCompositionRecord,
    DeterministicComposer,
    LayoutCatalog,
    LayoutSpec,
    MultiCutPlanner,
    cache_composer_font,
)
from .creative import CreativeCompileResult, CreativeCompiler, CreativeSpec, CreativeValidationError
from .creative_batches import CreativeBatchPlanner, CreativeBatchRecord, project_batch
from .creative_intelligence import (
    CreativeDirector,
    CreativeMode,
    PromptPlan,
    PromptPlanner,
    ShotRole,
    project_plan_to_creative_spec,
)
from .domain import Asset, AssetInput, ErrorDetail, JobRequest, JobStatus, Provenance
from .evaluator import (
    CreativeEvaluationError,
    CreativeEvaluator,
    EvaluationRequest,
    HostCreativeEvaluator,
)
from .events import (
    JobEventBus,
    JobSubscription,
    ModelOperationEventBus,
    ModelOperationSubscription,
    SessionEventBus,
    SessionSubscription,
)
from .environment import setup_snapshot
from .host.client import ControlDeckHostClient, HostApiError, HostIdentity
from .host.ai import HostAIGateway
from .host.files import GrantContentTooLarge, commit_file, read_grant, require_grant_id
from .host.jobs import HostExecution
from .jobs import JobManager, ProfileResolutionError
from .m5_companion import profile_documents as m5_profile_documents
from .model_evaluator import H3ModelEvaluator, unmeasured_lora_bases
from .model_viewer import ModelViewerError, ModelViewerSession
from .models.adapters import is_runnable
from .model_manager import MAX_MANAGED_MODEL_DOWNLOAD_BYTES, ModelOperationManager
from .models import (
    ModelOperationError,
    ModelRegistry,
    ModelRegistryError,
    TERMINAL_MODEL_OPERATION_STATES,
)
from .models.generation_defaults import (
    presets as generation_presets,
    resolution_buckets,
    summary as generation_summary,
)
from .paths import contained
from .prompt_recipes import H3PromptRecipe, PromptRecipeError, PromptRecipeRequest
from .profiles import ProfileInput, ReferenceCollectionInput
from .scene_backup_transport import SceneBackupSession
from .scenes import SceneCatalog, SceneError
from .scene_workspace import SceneWorkspace
from .host.security import reject_host_paths, require_host_service, require_host_service_headers
from .preferences import PreferenceError
from .reference_intelligence import (
    REFERENCE_FOCUSES,
    ReferenceAnalysisCache,
    ReferenceIntelligence,
    ReferenceIntelligenceError,
    analysis_summary,
)
from .image_evaluation import measure_image_model
from .store import AssetInUse, Store, utc_now
from .thumbnails import ThumbnailError

# workspace は base64 でしか運べない。これを超えるものは縮小版を返す。
WORKSPACE_TRANSPORT_LIMIT = 12 * 1024 * 1024
# 1 度に運ぶ生の量。base64 で 4/3 に膨らむので、socket の message 上限に
# 収まるところに置く。
ASSET_CHUNK_BYTES = 4 * 1024 * 1024
from .validators import validate_png


REPOSITORY_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
SCHEMAS_DIR = REPOSITORY_ROOT / "schemas"
FRONTEND_DIR = REPOSITORY_ROOT / "frontend"
HealthState = Literal["healthy", "degraded", "unavailable", "setup_required"]
MAX_CONTEXT_IMAGE_BYTES = 64 * 1024 * 1024
MAX_CONTEXT_IMAGE_PIXELS = 100_000_000
TERMINAL_JOB_STATES = {"succeeded", "failed", "canceled"}
JOB_EVENT_INTERVAL_SEC = 0.2


def workspace_test_response_delay_sec() -> float:
    if os.environ.get("MEDIA_FORGE_ENABLE_TEST_ENDPOINTS") != "1":
        return 0.0
    try:
        requested = float(os.environ.get("MEDIA_FORGE_TEST_WORKSPACE_DELAY_SEC", "0"))
    except ValueError:
        return 0.0
    return min(max(requested, 0.0), 2.0)


class HealthUpdate(BaseModel):
    status: HealthState


class HostFileRoundtrip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read_grant_id: str
    export_grant_id: str
    filename: str


def _unavailable(reason: str, message: str) -> dict[str, Any]:
    return {
        "state": "unavailable",
        "reason_code": reason,
        "message": message,
        "action": {"kind": "open_route", "route": "/x/media-forge/workspace/settings"},
    }



logger = logging.getLogger("uvicorn.error")

# session snapshot の分量。boot 1 往復に収める範囲で、旧 boot と同じ見え方を保つ。
SESSION_RECENT_LIMIT = 4
SESSION_JOB_LIMIT = 100


def _error_code(exc: BaseException) -> str:
    """既知の code 付き例外はその code を、それ以外は総称の code を返す。"""
    code = getattr(exc, "code", None)
    return code if isinstance(code, str) and code else "session_part_unavailable"


def create_app(
    settings: Settings | None = None,
    *,
    host_client: ControlDeckHostClient | None = None,
    creative_evaluator: CreativeEvaluator | None = None,
    native_model_evaluator: H3ModelEvaluator | None = None,
    model_download_origin: str = "https://huggingface.co",
    model_download_transport: httpx.AsyncBaseTransport | None = None,
    blender_download_transport: httpx.AsyncBaseTransport | None = None,
    blender_manifest_path: Path | None = None,
    blender_catalog_path: Path | None = None,
    blender_web_manifest_path: Path | None = None,
    blender_preflight_script: Path | None = None,
    blender_session_controller: Any | None = None,
) -> FastAPI:
    resolved = settings or Settings.from_env()
    trusted_blender_manifest = blender_manifest_path or (
        REPOSITORY_ROOT / "config/blender-runtime.json"
    )
    trusted_blender_catalog = blender_catalog_path
    if trusted_blender_catalog is None and blender_manifest_path is None:
        trusted_blender_catalog = REPOSITORY_ROOT / "config/blender-runtime-catalog.json"
    trusted_blender_preflight = blender_preflight_script or (
        REPOSITORY_ROOT / "worker_packs/blender/preflight.py"
    )
    trusted_blender_web_manifest = blender_web_manifest_path or (
        REPOSITORY_ROOT / "config/blender-web-runtime.json"
    )
    store = Store(resolved.data_dir)
    scenes = SceneCatalog(store)
    standalone_model_viewer = ModelViewerSession(store)
    standalone_scene_backups = SceneBackupSession(store)
    host = host_client or ControlDeckHostClient(
        resolved.control_deck_url,
        timeout_sec=resolved.host_request_timeout_sec,
    )
    ai_gateway = HostAIGateway(host)
    creative_director = CreativeDirector(PromptPlanner(ai_gateway))
    prompt_recipe = H3PromptRecipe(ai_gateway)
    reference_intelligence = ReferenceIntelligence(
        ai_gateway,
        ReferenceAnalysisCache(resolved.data_dir / "reference-analysis-cache"),
        timeout_sec=resolved.host_ai_timeout_sec,
    )
    evaluator = creative_evaluator or HostCreativeEvaluator(
        ai_gateway, timeout_sec=resolved.host_ai_timeout_sec
    )
    custom_models = CustomModelCatalog(
        resolved.data_dir / "custom-models.json",
        origin=model_download_origin,
        transport=model_download_transport,
        max_download_bytes=MAX_MANAGED_MODEL_DOWNLOAD_BYTES,
    )
    blender_runtimes = BlenderRuntimeResolver(
        registry_path=resolved.blender_runtime_registry,
        managed_root=resolved.blender_managed_runtime_root,
        legacy_root=resolved.blender_legacy_runtime_root,
        manifest_path=trusted_blender_manifest,
        trusted_worker=REPOSITORY_ROOT / "worker_packs/blender/compile_asset.py",
        catalog_path=trusted_blender_catalog,
    )
    scene_workspace = SceneWorkspace(
        store,
        blender_runtimes,
        REPOSITORY_ROOT / "worker_packs/blender/scene_document.py",
        process_timeout_sec=resolved.blender_timeout_sec,
    )
    try:
        blender_runtimes.register_legacy()
    except BlenderRuntimeRegistryError as exc:
        logger.warning("Blender runtime registration is unavailable: %s", exc.code)
    blender_web_pack = BlenderWebPack(
        trusted_blender_web_manifest,
        resolved.blender_web_runtime_root,
    )
    blender_runtime_operations = BlenderRuntimeManager(
        store,
        blender_runtimes,
        manifest_path=trusted_blender_manifest,
        preflight_script=trusted_blender_preflight,
        download_root=resolved.blender_download_root,
        catalog_path=trusted_blender_catalog,
        web_pack=blender_web_pack,
        web_download_root=resolved.blender_web_download_root,
        transport=blender_download_transport,
    )
    blender_sessions = BlenderSessionManager(
        store,
        scene_workspace,
        blender_runtimes,
        blender_web_pack,
        runner=REPOSITORY_ROOT / "worker_packs/blender/web_session_runner.py",
        bootstrap=REPOSITORY_ROOT / "worker_packs/blender/gui_session_bootstrap.py",
        preferences_bootstrap=REPOSITORY_ROOT / "worker_packs/blender/gui_preferences.py",
        controller=blender_session_controller,
    )

    manager = JobManager(
        store,
        worker_timeout_sec=resolved.worker_timeout_sec,
        blender_timeout_sec=resolved.blender_timeout_sec,
        host_client=host,
        lease_renew_sec=resolved.host_lease_renew_sec,
        model_manifest=resolved.model_manifest,
        model_catalog_manifest=resolved.model_catalog_manifest,
        model_store_root=resolved.model_store_root,
        hf_home=resolved.hf_home,
        image_runtime_python=resolved.image_runtime_python,
        video_runtime_python=resolved.video_runtime_python,
        native_media_runtime_root=resolved.native_media_runtime_root,
        wan_source_root=resolved.wan_source_root,
        creative_evaluator=evaluator,
        extra_manifests=custom_models.overlay,
        blender_runtime_resolver=blender_runtimes,
    )

    # 演出の立案と検証を job の中で行うための入口。画面が順番に呼んでいた頃は
    # 途中結果がページにしか無く、タブを閉じると失われていた。
    async def direct_for_job(job: Job, spec: dict[str, Any], mode: str) -> dict[str, Any] | None:
        identity = manager.host_identity(job.id)
        directed = await creative_director.direct(
            identity, job.request.intent, spec,
            mode=mode,
            reference_context=job.request.constraints.get("reference_context") or [],
        )
        return directed.model_dump(mode="json") if hasattr(directed, "model_dump") else directed

    async def validate_for_job(
        job: Job, request: JobRequest, spec: dict[str, Any], plan: Any
    ) -> JobRequest:
        identity = manager.host_identity(job.id)
        profile_snapshot = manager.resolve_profiles(request)
        available_references = {item.asset_id for item in request.inputs} | set(
            profile_snapshot.get("reference_asset_ids", [])
        )
        capability_value = await capability_document(identity)
        return compile_creative(
            request,
            CreativeSpec.model_validate(spec),
            capabilities=capability_value["capabilities"],
            available_references=available_references,
            director_plan=PromptPlan.model_validate(plan) if plan else None,
            reference_context=job.request.constraints.get("reference_context") or [],
        ).request

    manager.creative_director = direct_for_job
    manager.creative_validate = validate_for_job
    events = JobEventBus()
    store.observe(events.publish)
    model_events = ModelOperationEventBus()
    store.observe_model_operations(model_events.publish)
    session_events = SessionEventBus()
    store.observe_session(session_events.publish)
    creative_compiler = CreativeCompiler.load(resolved.creative_template_manifest)
    creative_batch_planner = CreativeBatchPlanner(creative_compiler)
    layout_catalog = LayoutCatalog.load(resolved.creative_layout_manifest)
    multi_cut_planner = MultiCutPlanner(creative_compiler, layout_catalog)
    deterministic_composer = DeterministicComposer()
    model_operations = (
        ModelOperationManager(
            store,
            model_manifest=resolved.model_manifest,
            catalog_manifest=resolved.model_catalog_manifest,
            model_store_root=resolved.model_store_root,
            hf_home=resolved.hf_home,
            model_in_use=manager.model_in_use,
            download_origin=model_download_origin,
            transport=model_download_transport,
            custom_models=custom_models,
        )
        if resolved.model_catalog_manifest is not None
        else None
    )
    native_runtime_root = resolved.native_media_runtime_root
    assert native_runtime_root is not None
    model_evaluations = native_model_evaluator or (
        H3ModelEvaluator(
            store,
            host,
            model_manifest=resolved.model_manifest,
            catalog_manifest=resolved.model_catalog_manifest,
            model_store_root=resolved.model_store_root,
            hf_home=resolved.hf_home,
            runtime_root=native_runtime_root,
            wan_runtime_python=resolved.wan_runtime_python,
            wan_source_root=resolved.wan_source_root,
            wan_evaluation_preset=resolved.wan_evaluation_preset,
            hunyuan_runtime_python=resolved.hunyuan_runtime_python,
            hunyuan_snapshot_root=resolved.hunyuan_snapshot_root,
            hunyuan_evaluation_preset=resolved.hunyuan_evaluation_preset,
            cogvideox2b_runtime_python=resolved.cogvideox2b_runtime_python,
            cogvideox2b_snapshot_root=resolved.cogvideox2b_snapshot_root,
            cogvideox2b_evaluation_preset=resolved.cogvideox2b_evaluation_preset,
            wan21_vace_runtime_python=resolved.wan21_vace_runtime_python,
            wan21_vace_snapshot_root=resolved.wan21_vace_snapshot_root,
            wan21_vace_evaluation_preset=resolved.wan21_vace_evaluation_preset,
            lease_renew_sec=resolved.host_lease_renew_sec,
            timeout_sec=resolved.model_evaluation_timeout_sec,
            # 自作モデルも測れるようにする。shipped manifest に居ないので、
            # custom entry を含んだ一覧を渡す。
            registry_loader=(
                (lambda: list(model_operations._registry().all()))
                if model_operations is not None else None
            ),
            image_runtime_python=resolved.image_runtime_python,
            image_measure=measure_image_model,
            record_measurement=custom_models.record_measurement,
        )
        if resolved.model_catalog_manifest is not None
        else None
    )
    dependency_tasks: set[asyncio.Task[None]] = set()

    def pending_lora_base_ids() -> list[str]:
        if model_operations is None or model_evaluations is None:
            return []
        try:
            return unmeasured_lora_bases(model_operations._registry().all())
        except (ModelRegistryError, OSError):
            return []

    def start_pending_lora_base_evaluations(identity: HostIdentity) -> None:
        """測れていない土台の評価を始める。既に一度試したものは触らない。

        以前は download 直後の in-process task だけが評価を始めていた。
        task は再起動で消えるので、数分かかる download が再起動を跨ぐと
        土台は永久に未計測のまま残った。要求のたびに帳尻を合わせれば、
        いつ落ちても次に開いたときに追いつく。

        失敗を自動で繰り返さない。一度 failed になった評価は、利用者が
        モデル管理から明示的に押し直すまで再開しない。
        """
        if model_evaluations is None:
            return
        attempted = {
            operation.model_id
            for operation in store.list_model_operations()
            if operation.action.value == "evaluate"
        }
        started = False
        for model_id in pending_lora_base_ids():
            if model_id in attempted:
                continue
            try:
                model_evaluations.evaluate(model_id, identity)
            except ModelOperationError as exc:
                # 握り潰さない。押しても何も起きない状態を作った原因がこれだった。
                logger.warning(
                    "could not start the base evaluation for %s: %s", model_id, exc.code
                )
                continue
            started = True
        if started:
            session_events.publish("model_operations")

    async def evaluate_after_install(
        install_operation_id: str,
        identity: HostIdentity,
    ) -> None:
        """Finish what a download started: measure the base a LoRA now has.

        A base only becomes selectable once it has been measured here, and the
        model that needs it may have arrived by any route — a LoRA pulling its
        base down with it, or someone adding the checkpoint on its own. Waiting
        for the next time a person opens the workspace leaves a download that
        finished unattended sitting unusable, which is what happened with
        Lykon/DreamShaper on 2026-08-28.
        """
        while True:
            operation = store.get_model_operation(install_operation_id)
            if operation.state.value == "ready":
                break
            if operation.state.value in {"failed", "canceled"}:
                return
            await asyncio.sleep(0.5)
        start_pending_lora_base_evaluations(identity)

    def follow_install(operation_id: str, identity: HostIdentity) -> None:
        task = asyncio.create_task(
            evaluate_after_install(operation_id, identity),
            name=f"install-follow-up-{operation_id}",
        )
        dependency_tasks.add(task)
        task.add_done_callback(dependency_tasks.discard)
    workspace_test_delay_pending = True

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        store.initialize()
        scene_workspace.initialize()
        standalone_scene_backups.initialize()
        await manager.start()
        await blender_runtime_operations.start()
        await blender_sessions.start()
        if model_operations is not None:
            await model_operations.start()
        if model_evaluations is not None:
            await model_evaluations.start()
        yield
        for task in dependency_tasks:
            task.cancel()
        await asyncio.gather(*dependency_tasks, return_exceptions=True)
        if model_evaluations is not None:
            await model_evaluations.stop()
        if model_operations is not None:
            await model_operations.stop()
        await blender_sessions.stop()
        await blender_runtime_operations.stop()
        await manager.stop()
        await asyncio.to_thread(standalone_model_viewer.cleanup)
        await asyncio.to_thread(standalone_scene_backups.shutdown_cleanup)
        await host.close()

    app = FastAPI(title="ControlDeck Media Forge", version=__version__, lifespan=lifespan)
    # workspace は 1 応答に markup と style と script を全部畳んで返すので
    # 356 KB あった。手元では 15 ms でも、Tailscale の relay 越しではその差が
    # そのまま待ち時間になる。gzip で 91 KB（74% 減）。
    # 最小値は 1 KB。小さな JSON まで圧縮しても、CPU を使うだけで速くならない。
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.state.health_override = None
    app.state.store = store
    app.state.scenes = scenes
    app.state.scene_workspace = scene_workspace
    app.state.scene_backups = standalone_scene_backups
    app.state.jobs = manager
    app.state.job_events = events
    app.state.model_operations = model_operations
    app.state.model_evaluations = model_evaluations
    app.state.model_operation_events = model_events
    app.state.creative_compiler = creative_compiler
    app.state.creative_batch_planner = creative_batch_planner
    app.state.multi_cut_planner = multi_cut_planner
    app.state.deterministic_composer = deterministic_composer
    app.state.creative_evaluator = evaluator
    app.state.creative_director = creative_director
    app.state.reference_intelligence = reference_intelligence
    app.state.host = host
    app.state.blender_runtimes = blender_runtimes
    app.state.blender_runtime_operations = blender_runtime_operations
    app.state.blender_sessions = blender_sessions
    app.state.blender_web_pack = blender_web_pack
    app.state.standalone_model_viewer = standalone_model_viewer
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/viewer-runtime.js", include_in_schema=False)
    async def viewer_runtime() -> FileResponse:
        """Lazy CORS-readable module for an opaque sandboxed workspace."""
        return FileResponse(
            FRONTEND_DIR / "three-viewer.js",
            media_type="text/javascript",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cross-Origin-Resource-Policy": "cross-origin",
                "Cache-Control": "public, max-age=31536000, immutable",
            },
        )

    @app.get("/blender-web-client/{relative:path}", include_in_schema=False)
    async def blender_web_client(relative: str) -> FileResponse:
        """Serve only manifest-pinned noVNC modules to the opaque workspace."""
        try:
            path = blender_web_pack.client_file(relative)
        except BlenderWebPackError as exc:
            raise HTTPException(status_code=404, detail={"code": exc.code}) from exc
        return FileResponse(
            path,
            media_type="text/javascript",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cross-Origin-Resource-Policy": "cross-origin",
                "Cache-Control": "public, max-age=31536000, immutable",
                "X-Content-Type-Options": "nosniff",
            },
        )

    async def serve_blender_rfb(
        websocket: WebSocket,
        owner: str,
        session_id: str,
        *,
        revalidate: Callable[[], Awaitable[bool]] | None = None,
    ) -> None:
        reserved = False
        try:
            socket_path = await blender_sessions.acquire_gateway(owner, session_id)
            reserved = True
            await relay_rfb(websocket, socket_path, revalidate=revalidate)
        except BlenderSessionError as exc:
            await websocket.close(
                code=4409 if exc.code == "blender_session_already_connected" else 4404,
                reason="Blender session is unavailable",
            )
        finally:
            if reserved:
                await blender_sessions.release_gateway(session_id)

    @app.websocket("/blender/sessions/{session_id}/rfb")
    async def host_blender_rfb(websocket: WebSocket, session_id: str) -> None:
        try:
            identity = await require_host_service_headers(websocket.headers, host)
        except HTTPException:
            await websocket.close(code=4401, reason="invalid host service token")
            return
        credential_headers = {
            "Authorization": identity.authorization,
            "X-Control-Deck-Addon-ID": identity.addon_id,
        }

        async def revalidate() -> bool:
            try:
                current = await host.authenticate(credential_headers)
            except HostApiError:
                return False
            return current.addon_id == identity.addon_id and current.subject == identity.subject

        await serve_blender_rfb(
            websocket, preferences.subject_of(identity), session_id, revalidate=revalidate
        )

    @app.websocket("/workspace-api/blender/sessions/{session_id}/rfb")
    async def standalone_blender_rfb(websocket: WebSocket, session_id: str) -> None:
        origin = websocket.headers.get("origin", "")
        host_header = websocket.headers.get("host", "")
        parsed_origin = urlsplit(origin)
        parsed_host = urlsplit(f"//{host_header}")
        if (
            parsed_origin.scheme not in {"http", "https"}
            or parsed_origin.netloc != host_header
            or parsed_origin.path not in {"", "/"}
            or parsed_origin.query
            or parsed_origin.fragment
            or parsed_host.hostname not in {"127.0.0.1", "::1", "localhost"}
        ):
            await websocket.close(code=4403, reason="same-loopback origin required")
            return
        await serve_blender_rfb(websocket, preferences.STANDALONE_SUBJECT, session_id)

    async def authorize_host(request: Request) -> HostIdentity:
        return await require_host_service(request, host)

    def public_model(item: ModelDescriptor) -> dict[str, Any]:
        value: dict[str, Any] = {
            "id": item.model_id,
            "family": item.family,
            "version": item.version,
            "revision": item.revision,
            "license": item.license,
            "runtime_adapter": item.runtime_adapter,
            "capabilities": list(item.capabilities),
            "state": item.state,
            "installed": item.installed,
            "healthy": item.healthy,
            "measured_vram_bytes": item.measured_vram_bytes,
            "measured_runtime_sec": item.measured_runtime_sec,
            "measurement_confidence": item.measurement_confidence,
            # LoRA は「使えるモデル」ではない。画面が本体と混ぜて出さないよう、
            # 種別と、どの系統に載せられるかをここで言う。
            "kind": "lora" if item.is_lora else "model",
            "base_model": item.base_model,
            "trigger_words": list(item.trigger_words),
        }
        if item.runtime_adapter.startswith("diffusers.") and item.installed:
            # 何が決まっていて何が決まっていないかは、判定した側が言う。
            # UI で組み立てると同じ判断が 2 か所に分かれて片方だけ直る。
            value["generation"] = {
                "steps": item.default_steps,
                "steps_source": item.default_steps_source,
                "native_width": item.native_width,
                "native_height": item.native_height,
                "guidance_scale": item.guidance_scale,
                "sizes": [
                    list(size) for size in resolution_buckets(item.native_width)
                ] if item.native_width else [],
                "presets": [
                    dict(preset) for preset in generation_presets(
                        item.default_steps or 30,
                        item.default_steps_source,
                        item.guidance_scale,
                    )
                ],
                **generation_summary(
                    steps=item.default_steps,
                    steps_source=item.default_steps_source,
                    native_width=item.native_width,
                    native_height=item.native_height,
                    guidance_scale=item.guidance_scale,
                ),
            }
        if item.source is not None:
            value.update({
                "hardware_backends": list(item.hardware_backends),
                "display_name": item.display_name,
                "domains": list(item.domains),
                "media_types": list(item.media_types),
                "description": item.description,
                "approx_download_bytes": item.approx_download_bytes,
                "source": {
                    "kind": item.source.kind,
                    "repo_id": item.source.repo_id,
                    "revision": item.source.revision,
                },
                "ownership": item.ownership,
                # 測れることと使えることは別。走らせる worker が居ないモデルは、
            # 評価しても選べるようにはならない。画面がそれを言えるようにする。
            "has_runtime": is_runnable(item.runtime_adapter),
            # 動画の作り方はモデルごとに違う。画面が共通の決め打ちを持つと、
            # どれかのモデルで「選べるのに作れない」値を出すことになる。
            # 歩数もここへ入れる。`generation` は diffusers 経路にしか付かず、
            # native の動画モデルには届かない。画面が測定基準の `measured_steps`
            # で代用すると、測り直した歩数がそのまま既定にすり替わる。
            # 倍率と、どこまで受けるかはモデルが言う。画面が決め打ちすると、
            # 別の倍率の重みを足したとき黙って外れる。
            **({"upscale": dict(item.upscale)} if item.upscale else {}),
            **({"video": {
                **dict(item.video),
                **({"default_steps": item.default_steps}
                   if item.default_steps is not None else {}),
            }} if item.video else {}),
            "supports_lora": item.supports_lora,
                "max_references": item.max_references,
                "reference_roles": list(item.reference_roles),
                "supports_reference_strength": item.supports_reference_strength,
                "recommended_profiles": list(item.recommended_profiles),
                "gated": item.gated,
                "license_notice": item.license_notice,
            })
        return value

    def load_all_models() -> list[ModelDescriptor]:
        """The one list everything reads.

        Three call sites used to load this separately, and the custom entries
        were added to some of them. A model could then be offered in the
        picker and refused by routing in the same breath.
        """
        extra_models, extra_catalog, measurements = custom_models.overlay()
        return list(ModelRegistry.load(
            resolved.model_manifest,
            hf_home=resolved.hf_home,
            catalog_manifest=resolved.model_catalog_manifest,
            model_store_root=resolved.model_store_root,
            extra_models=extra_models,
            extra_catalog=extra_catalog,
            measurements=measurements,
        ).all())

    def model_catalog() -> dict[str, Any]:
        try:
            models = load_all_models()
        except ModelRegistryError as exc:
            raise HTTPException(status_code=503, detail={"code": "model_registry_invalid"}) from exc
        return {
            "items": [public_model(item) for item in models]
        }

    def video_capability(capability: str) -> dict[str, Any]:
        """動画は runtime も別なので、モデルだけ揃っても走らない。

        以前はここを `video_runtime_not_adopted` で固定していた。実測で
        latency も VRAM も相場どおりと分かったので、固定をやめて実態から出す。
        """
        if not resolved.video_runtime_python.is_file():
            return {"state": "unavailable", "reason": "video_runtime_not_installed", "local_only": True}
        return image_capability(capability)

    def image_capability(capability: str, *, fake_fallback: bool = False) -> dict[str, Any]:
        try:
            models = load_all_models()
        except ModelRegistryError:
            return {"state": "unavailable", "reason": "model_registry_invalid", "local_only": True}
        if any(
            item.state.value == "available" and item.installed and item.healthy
            and capability in item.capabilities
            for item in models
        ):
            confidence = next(
                item.measurement_confidence
                for item in models
                if item.state.value == "available" and item.installed and item.healthy
                and capability in item.capabilities
            )
            return {"state": "available", "implementation": "local", "confidence": confidence, "local_only": True}
        if any(item.state.value == "available" and capability in item.capabilities for item in models):
            return {"state": "unavailable", "reason": "model_not_installed", "local_only": True}
        if fake_fallback:
            return {"state": "available", "implementation": "fake", "confidence": "low", "local_only": True}
        return {"state": "unavailable", "reason": "capability_not_installed", "local_only": True}

    async def submit_hosted(
        value: JobRequest,
        identity: HostIdentity,
        *,
        workload_class: str,
    ) -> dict[str, Any]:
        missing = {"jobs.write", "resources.acquire"} - identity.granted_capabilities
        if missing:
            raise HTTPException(status_code=403, detail={"code": "host_capability_not_granted"})
        try:
            value = apply_asset_brief(value)
        except AssetBriefError as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)[:300]}) from exc
        try:
            profile_snapshot = manager.resolve_profiles(value)
        except ProfileResolutionError as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code}) from exc
        try:
            attached = await host.create_or_attach_job(identity, title="Media Forge image generation")
        except HostApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"code": exc.code}) from exc
        host_job = attached.get("job")
        if not isinstance(host_job, dict) or not isinstance(host_job.get("id"), str):
            raise HTTPException(status_code=502, detail={"code": "invalid_host_response"})
        execution = HostExecution(
            identity=identity,
            host_job_id=host_job["id"],
            workload_class=workload_class,
            owns_terminal=attached.get("created") is True,
        )
        return manager.submit_hosted(
            value,
            execution,
            profile_snapshot=profile_snapshot,
        ).model_dump(mode="json")

    # LLM が VRAM を占めていると、空きに合わせた置き直しを挟むぶん生成が伸びる。
    # 実測（R9700 / LLM 25GB 常駐）では 110 秒に収まる回と収まらない回があり、
    # 収まらないと job は動いているのに 504 を返して捨てていた。ControlDeck 側の
    # 上限（600 秒）に合わせる。
    async def wait_for_terminal(job_id: str, timeout: float = 600.0) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            job = store.get_job(job_id)
            if job.status.value in {"succeeded", "failed", "canceled"}:
                return job.model_dump(mode="json")
            await asyncio.sleep(0.02)
        raise HTTPException(status_code=504, detail={"code": "job_wait_timeout", "job_id": job_id})

    def submitted_reference(value: dict[str, Any]) -> dict[str, Any]:
        return {"job_id": value["id"], "status": value["status"], "asset_ids": value["asset_ids"]}

    def placement_manifest(request_input: object) -> PlacementManifest:
        """Accept either the long-standing single placement or a batch.

        The singular form is what every existing caller sends and it keeps
        working unchanged, including its response shape. The batch form exists
        because placing related assets one call at a time made the outcome hard
        to confirm without going to the filesystem.
        """
        if not isinstance(request_input, dict):
            raise HTTPException(
                status_code=422, detail={"code": "invalid_project_asset_placement"}
            )
        try:
            if "items" in request_input:
                return PlacementManifest.model_validate(request_input)
            single = ProjectAssetPlacement.model_validate(request_input)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "invalid_project_asset_placement"}
            ) from exc
        return PlacementManifest(
            output_grant_id=single.output_grant_id,
            items=[PlacementItem(asset_id=single.asset_id, filename=single.filename)],
        )

    def placement_response(
        request_input: object, receipts: list[PlacementReceipt], *, partial: bool
    ) -> dict[str, Any]:
        """Answer in the shape the caller asked in, and never overclaim.

        ControlDeck commits one file atomically. A batch of N is N separate
        commits, so the response reports per-item outcomes and says plainly
        that the batch is not all-or-nothing.
        """
        batch = isinstance(request_input, dict) and "items" in request_input
        if not batch:
            receipt = receipts[0]
            return {
                "asset_id": receipt.host_asset_id,
                "media_asset_id": receipt.source_asset_id,
                "name": receipt.filename,
                "mime_type": receipt.media_type,
                "size": receipt.size_bytes,
                "sha256": receipt.sha256,
                "receipt": receipt.model_dump(mode="json"),
            }
        return {
            "receipts": [item.model_dump(mode="json") for item in receipts],
            "committed_count": sum(1 for item in receipts if item.committed),
            "requested_count": len(receipts),
            "partial": partial,
            # Host が原子的に扱えるのは 1 ファイルである。N 件を「全部か無か」と
            # 名乗ると、部分的に書かれた状態を呼び出し側が見落とす。
            "atomic": False,
        }

    def apply_asset_brief(value: JobRequest) -> JobRequest:
        """Resolve the output canvas from the asset's purpose, before generation.

        Without this the geometry decision fell to the worker's own fallback,
        which knows nothing about what the image is for: a request describing a
        "wide landscape" title background arrived with empty constraints and
        came back 1024x1024.

        The brief rides inside the already free-form ``constraints`` object, so
        no public schema changes. Editing keeps its existing source-derived
        geometry; only generation resolves a canvas here.
        """
        if value.operation != "image.generate":
            # 編集は元画像から寸法を導く。用途既定で上書きしない。
            return value
        brief_value = value.constraints.get("asset_brief")
        brief = parse_brief(brief_value)
        if brief is None:
            # 既存の呼び出し側は用途を散文でしか書かない。構造的な語だけを
            # 決定的に拾う。確信が持てなければ何も推論せず従来どおりにする。
            brief = infer_brief_from_intent(value.intent)
        if brief is None:
            return value
        width = value.constraints.get("width")
        height = value.constraints.get("height")
        explicit_width = width if isinstance(width, int) and not isinstance(width, bool) else None
        explicit_height = height if isinstance(height, int) and not isinstance(height, bool) else None
        resolved = resolve_layout(
            brief,
            envelope=size_envelope(),
            explicit_width=explicit_width,
            explicit_height=explicit_height,
        )
        if resolved is None:
            return value
        constraints = {
            **value.constraints,
            **resolved.as_constraints(),
            # なぜこの寸法になったかを残す。provenance と UI が理由を出せる。
            "resolved_layout": resolved.document(),
        }
        return value.model_copy(update={"constraints": constraints})

    def host_job_input(payload: object) -> JobRequest:
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail={"code": "invalid_execution_envelope"})
        reject_host_paths(payload)
        try:
            return JobRequest.model_validate(payload.get("input", {}))
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_job_request"}) from exc

    @app.get("/health")
    async def health() -> dict[str, Any]:
        environment = setup_snapshot()
        token_state: str | dict[str, Any] = "available"
        status: HealthState = app.state.health_override or (
            environment.get("status", "setup_required") if environment else "setup_required"
        )
        payload: dict[str, Any] = {
            "status": status,
            "contract_version": "2.0",
            "contributions": {
                "navigation:workspace": "available",
                "embedded_view:workspace": "available",
                "command:create-media": token_state,
                "settings:settings": "available",
                "workflow_executor:media.generate": token_state,
                "agent_tool:media.capabilities": token_state,
                "agent_tool:media.generate": token_state,
                "agent_tool:media.inspect": token_state,
                "agent_tool:media.pack": token_state,
                "context_action:edit-image": token_state,
            },
            "setup": (
                [host_setup_item(item) for item in environment["setup"]]
                if environment
                else [
                    {
                        "id": "environment",
                        "label": "Media Forge environment",
                        "state": "missing",
                        "message": "Start the service with ./mf.sh serve",
                        "action": {
                            "kind": "open_route",
                            "route": "/x/media-forge/workspace/settings",
                        },
                    }
                ]
            ),
        }
        return payload

    @app.get("/api/v1/host-integration")
    async def host_integration() -> dict[str, Any]:
        return {
            "service_token_verifier": "control_deck_introspection",
            "resource_lease_bridge": "configured",
            "remote_jobs_bridge": "configured",
            "scoped_files_bridge": "configured",
            "control_deck_origin": resolved.control_deck_url,
            "known_host_limitations": [],
            "fallback": "none",
        }

    @app.post("/test/health")
    async def set_health(update: HealthUpdate) -> dict[str, Any]:
        if os.environ.get("MEDIA_FORGE_ENABLE_TEST_ENDPOINTS") != "1":
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        app.state.health_override = update.status
        return await health()

    @app.post("/test/host-files/roundtrip")
    async def host_file_roundtrip(update: HostFileRoundtrip, request: Request) -> dict[str, Any]:
        if os.environ.get("MEDIA_FORGE_ENABLE_TEST_ENDPOINTS") != "1":
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        identity = await authorize_host(request)
        if Path(update.filename).name != update.filename or update.filename in {"", ".", ".."}:
            raise HTTPException(status_code=422, detail={"code": "invalid_filename"})
        try:
            read_id = require_grant_id(update.read_grant_id)
            export_id = require_grant_id(update.export_grant_id)
            metadata, content = await read_grant(host, identity, read_id)
            attached = await host.create_or_attach_job(identity, title="Media Forge scoped file bridge test")
            host_job_id = attached["job"]["id"]
            created = await host.create_output(identity, {
                "job_id": host_job_id,
                "grant_id": export_id,
                "filename": update.filename,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "content_type": "application/octet-stream",
            })
            await host.upload_output(identity, created["output_id"], content)
            committed = await host.commit_output(identity, created["output_id"])
            if attached.get("created") is True:
                await host.update_job(identity, host_job_id, {
                    "phase": "package",
                    "progress": {"completed": 1, "total": 1},
                    "status": "succeeded",
                    "result": {"asset_id": committed["asset_id"]},
                })
        except (HostApiError, KeyError, ValueError) as exc:
            code = exc.code if isinstance(exc, HostApiError) else "invalid_host_response"
            raise HTTPException(status_code=502, detail={"code": code}) from exc
        return {
            "source": {"grant_id": read_id, "name": metadata["name"], "size": len(content)},
            "output": committed,
        }

    def device_vram_bytes() -> int:
        """How much VRAM this machine actually has, or 0 when unknown.

        Needed to say whether a model can run here at all. Reported as 0 rather
        than guessed: claiming a model fits when we do not know is worse than
        saying we do not know.
        """
        environment = setup_snapshot()
        if not isinstance(environment, dict):
            return 0
        for item in environment.get("setup", []):
            if isinstance(item, dict) and item.get("id") == "gpu_memory":
                total = item.get("total_bytes")
                if isinstance(total, int) and not isinstance(total, bool) and total > 0:
                    return total
        return 0

    def installed_families() -> set[str]:
        """導入済みの checkpoint が属する系統。

        LoRA を載せられる先があるかを、この集合で判断する。
        """
        from .models.generation_defaults import normalize_base_model

        try:
            models = load_all_models()
        except ModelRegistryError:
            return set()
        return {
            normalize_base_model(item.base_model)
            for item in models
            if item.installed and item.healthy and not item.is_lora and item.base_model
        } - {""}

    def annotate_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """検索結果に、こちら側で既にどうなっているかを添える。

        「一覧に登録した」と「実際に落とした」は別である。1 つの語にまとめて
        いたので、登録しただけの repository が「追加済み」と出て、ダウンロード
        が始まらない理由が画面から読み取れなかった。
        """
        listed = {
            item["registry"]["model_id"]
            for item in custom_models.entries()
            if isinstance(item.get("registry"), dict)
        }
        installed = {
            str(item.get("model_id"))
            for item in (model_operations.catalog().get("items", []) if model_operations else [])
            if item.get("installed")
        }
        return [
            {
                **row,
                "already_added": row["repo_id"] in listed | installed,
                "catalog_state": (
                    "installed" if row["repo_id"] in installed
                    else "listed" if row["repo_id"] in listed else None
                ),
            }
            for row in rows
        ]

    def host_setup_item(item: Any) -> dict[str, Any]:
        """Emit only what the Host contract defines for a setup checklist item.

        The local environment file carries more than the Host asks for —
        gpu_memory keeps `total_bytes` because runnability needs the number and
        digging it back out of a sentence is not something to build on. Handing
        that field to the Host is a different matter: SetupChecklistItem forbids
        extras, so one unknown key fails the whole health report and the add-on
        reads as unreachable while the service is answering normally. That is
        what happened. Media Forge vocabulary stops at this boundary.
        """
        if not isinstance(item, dict):
            return {"id": "environment", "label": "Media Forge environment", "state": "error"}
        return {
            key: value for key, value in item.items()
            if key in {"id", "label", "state", "detail", "message", "action"}
        }

    def size_envelope() -> dict[str, Any]:
        """Derive the size bounds the UI may offer from installed models.

        Conservative on purpose: the workspace must not present a preset that a
        routed model would reject after the user pressed the button.
        """
        fallback = {
            "min_side": 256,
            "max_side": 1024,
            "multiple_of": 16,
            "max_pixels": 1024 * 1024,
            "max_count": 8,
            "max_reference_assets": 4,
            "reference_roles": [
                "identity", "style", "pose", "composition", "clothing", "palette", "prop", "environment"
            ],
            "supports_reference_strength": False,
            "envelope_source": "fallback",
        }
        try:
            models = load_all_models()
        except ModelRegistryError:
            return fallback
        usable = [
            item for item in models
            if item.state.value == "available" and item.installed and item.healthy
            and "image.text_to_image" in item.capabilities
        ]
        if not usable:
            return fallback
        reference_limits = [item.max_references for item in usable if item.max_references > 0]
        role_sets = [set(item.reference_roles) for item in usable if item.max_references > 0]
        shared_roles = set.intersection(*role_sets) if role_sets else set()
        return {
            "min_side": 256,
            "max_side": min(min(item.max_width, item.max_height) for item in usable),
            "multiple_of": 16,
            "max_pixels": min(item.max_pixels for item in usable),
            "max_count": 8,
            "max_reference_assets": min(reference_limits) if reference_limits else 0,
            "reference_roles": sorted(shared_roles),
            "supports_reference_strength": bool(reference_limits) and all(
                item.supports_reference_strength for item in usable if item.max_references > 0
            ),
            "envelope_source": "measured",
        }

    def size_presets(envelope: dict[str, Any]) -> list[dict[str, Any]]:
        """Presets are clamped into the envelope instead of being hardcoded."""
        multiple = int(envelope["multiple_of"])
        limit = int(envelope["max_side"])

        def fit(width: int, height: int) -> tuple[int, int]:
            scale = min(1.0, limit / max(width, height))
            values = []
            for side in (width, height):
                bounded = max(int(envelope["min_side"]), int(side * scale))
                values.append(bounded - bounded % multiple)
            return values[0], values[1]

        square = fit(1024, 1024)
        landscape = fit(1024, 576)
        portrait = fit(576, 1024)
        return [
            {"id": "square", "label_key": "size.square", "width": square[0], "height": square[1]},
            {"id": "landscape", "label_key": "size.landscape", "width": landscape[0], "height": landscape[1]},
            {"id": "portrait", "label_key": "size.portrait", "width": portrait[0], "height": portrait[1]},
        ]

    async def capability_document(identity: HostIdentity | None = None) -> dict[str, Any]:
        text_direction_available = await creative_director.available(identity)
        evaluator_available = await evaluator.available(identity)
        semantic_available = evaluator_available
        return {
            "contract_version": "1.0",
            "capabilities": {
                "image.text_to_image": image_capability("image.text_to_image", fake_fallback=True),
                "image.single_reference_edit": image_capability("image.single_reference_edit"),
                "image.inpaint": image_capability("image.inpaint"),
                "image.outpaint": image_capability("image.outpaint"),
                "image.variation": image_capability("image.variation"),
                "image.multi_reference_edit": image_capability("image.multi_reference_edit"),
                "image.strict_edit": image_capability("image.strict_edit"),
                # 拡大は作り直さない。同じ絵からは同じ絵が出る。
                "image.upscale": image_capability("image.upscale"),
                # ブレ補正も作り直さない。寸法も変わらない。
                "image.deblur": image_capability("image.deblur"),
                # 塗った所を周りから埋める。描き直さないので境目が出ない。
                "image.erase": image_capability("image.erase"),
                # 塗った所を「指して」直す。守る範囲ではないので、絵全体が
                # 変わる。保証が違うので inpaint とは別の capability である。
                "image.masked_edit": image_capability("image.masked_edit"),
                "image.semantic_review": (
                    {"state": "available"}
                    if semantic_available
                    else {"state": "unavailable", "reason": "vision_analyzer_unavailable"}
                ),
                "image.creative_evaluation": (
                    {"state": "available"}
                    if evaluator_available
                    else {"state": "unavailable", "reason": "vision_analyzer_unavailable"}
                ),
                "creative.text_direction": (
                    {"state": "available"}
                    if text_direction_available
                    else {"state": "unavailable", "reason": "text_generator_unavailable"}
                ),
                "creative.reference_intelligence": {
                    "state": "available",
                    "semantic_state": "available" if semantic_available else "unavailable",
                    "semantic_reason": None if semantic_available else "vision_analyzer_unavailable",
                },
                "asset.m5_companion_pack": {"state": "available"},
                "asset.3d_project_pack": (
                    {"state": "available", "profile": "3d.project.glb"}
                    if blender_runtimes.resolve_g8() is not None
                    else {"state": "unavailable", "reason": "runtime_not_installed"}
                ),
                # 旗を立てて回るのではなく、実際に走らせられるかで決める。
                # 実測済みの動画モデルと動画 runtime の両方が揃ったときだけ出す。
                "video.text_to_video": video_capability("video.text_to_video"),
                # 入力画像から動かす経路は worker にまだ無い。
                "video.image_to_video": {
                    "state": "unavailable",
                    "reason": "video_runtime_not_adopted",
                },
                "3d.image_to_3d": {"state": "unavailable", "reason": "planned_for_g9"},
            },
        }

    def compile_creative(
        request: JobRequest,
        creative_spec: CreativeSpec,
        *,
        capabilities: dict[str, Any],
        available_references: set[str],
        director_plan: PromptPlan | None = None,
        reference_context: list[dict[str, Any]] | None = None,
    ) -> CreativeCompileResult:
        compiled = creative_compiler.compile(
            request,
            creative_spec,
            capabilities=capabilities,
            envelope=size_envelope(),
            available_reference_ids=available_references,
        )
        if director_plan is None:
            return compiled
        plan = {**compiled.plan, "director": {
            **director_plan.model_dump(mode="json"),
            "source": "control-deck:text.generate",
            "reference_context": reference_context or [],
        }}
        value = compiled.request.model_dump(mode="json")
        value["constraints"] = {**value["constraints"], "creative_plan": plan}
        return CreativeCompileResult(request=JobRequest.model_validate(value), plan=plan)

    def batch_projection(record: CreativeBatchRecord) -> dict[str, Any]:
        jobs = []
        for job_id in record.child_job_ids:
            try:
                jobs.append(store.get_job(job_id))
            except KeyError:
                continue
        return project_batch(record, jobs)

    def params_director_mode(payload: dict[str, Any]) -> CreativeMode:
        value = payload.get("director_mode", "original")
        if value not in {"original", "refine", "art_direct"}:
            raise ValueError("director_mode is invalid")
        return value

    def accepted_reference_context(payload: dict[str, Any]) -> list[dict[str, Any]]:
        requested = payload.get("reference_analysis", [])
        if not isinstance(requested, list) or len(requested) > 4:
            raise ValueError("reference_analysis is invalid")
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in requested:
            if not isinstance(item, dict) or set(item) != {"asset_id", "focus"}:
                raise ValueError("reference_analysis is invalid")
            asset_id = item.get("asset_id")
            focus = item.get("focus")
            if not isinstance(asset_id, str) or focus not in REFERENCE_FOCUSES or asset_id in seen:
                raise ValueError("reference_analysis is invalid")
            asset = store.get_asset(asset_id)
            analysis = reference_intelligence.cache.read_analysis(asset.sha256)
            if analysis is None or analysis.asset_hash != asset.sha256:
                raise ReferenceIntelligenceError(
                    "reference_analysis_missing", "Accepted reference analysis is not cached"
                )
            result.append({
                "asset_id": asset_id,
                "asset_hash": asset.sha256,
                **analysis_summary(analysis, focus),
            })
            seen.add(asset_id)
        return result

    async def analyze_reference(
        payload: dict[str, Any], identity: HostIdentity | None,
    ) -> dict[str, Any]:
        if set(payload) != {"asset_id"} or not isinstance(payload.get("asset_id"), str):
            raise ValueError("reference analysis accepts one asset_id")
        asset = store.get_asset(payload["asset_id"])
        if not asset.mime_type.startswith("image/"):
            raise ReferenceIntelligenceError(
                "reference_image_invalid", "Reference analysis accepts image assets only"
            )
        return (await reference_intelligence.analyze(
            asset_id=asset.id,
            asset_sha256=asset.sha256,
            path=store.asset_path(asset.id),
            identity=identity,
        )).model_dump(mode="json")

    async def create_creative_batch(
        payload: dict[str, Any],
        submit_child: Callable[[JobRequest], Awaitable[dict[str, Any]]],
        identity: HostIdentity | None = None,
    ) -> dict[str, Any]:
        request = JobRequest.model_validate(payload.get("request"))
        creative_spec = CreativeSpec.model_validate(payload.get("creative_spec", {}))
        count = payload.get("count")
        profile_snapshot = manager.resolve_profiles(request)
        available_references = {
            item.asset_id for item in request.inputs
        } | set(profile_snapshot.get("reference_asset_ids", []))
        capability_value = await capability_document(identity)
        director_mode = params_director_mode(payload)
        reference_context = accepted_reference_context(payload)
        directed = None
        if (
            creative_spec.variation.axis == "pose"
            and director_mode != "original"
            and isinstance(count, int)
            and not isinstance(count, bool)
            and 2 <= count <= 4
        ):
            directed = await creative_director.action_variations(
                identity, request.intent, mode=director_mode, count=count,
                reference_context=reference_context,
            )
        if directed is not None and directed.assistance_used:
            projected, _ = project_plan_to_creative_spec(
                directed.plan, creative_spec.model_dump(mode="json")
            )
            creative_spec = CreativeSpec.model_validate(projected)
            batch_id, child_requests, child_plans = creative_batch_planner.plan_action_variations(
                request,
                creative_spec,
                directed.actions,
                directed.plan,
                reference_context=reference_context,
                capabilities=capability_value["capabilities"],
                envelope=size_envelope(),
                available_reference_ids=available_references,
            )
        else:
            batch_id, child_requests, child_plans = creative_batch_planner.plan(
                request,
                creative_spec,
                count,
                capabilities=capability_value["capabilities"],
                envelope=size_envelope(),
                available_reference_ids=available_references,
            )
        now = utc_now()
        record = store.create_creative_batch(CreativeBatchRecord(
            id=batch_id,
            axis=creative_spec.variation.axis,
            requested_count=count,
            child_plans=child_plans,
            created_at=now,
            updated_at=now,
        ))
        for child in child_requests:
            try:
                submitted = await submit_child(child)
                record.child_job_ids.append(str(submitted["id"]))
            except (HTTPException, ProfileResolutionError, KeyError, ValueError) as exc:
                code = (
                    str(exc.detail.get("code", "batch_child_submission_failed"))
                    if isinstance(exc, HTTPException) and isinstance(exc.detail, dict)
                    else exc.code if isinstance(exc, ProfileResolutionError)
                    else "batch_child_submission_failed"
                )
                record.submission_errors.append({"code": code, "message": str(exc)[:300]})
            record.updated_at = utc_now()
            store.update_creative_batch(record)
        result = batch_projection(record)
        if directed is not None:
            result["director"] = directed.model_dump(mode="json")
        return result

    async def cancel_creative_batch(batch_id: str) -> dict[str, Any]:
        record = store.get_creative_batch(batch_id)
        for job_id in record.child_job_ids:
            try:
                job = store.get_job(job_id)
                if job.status.value not in {"succeeded", "failed", "canceled"}:
                    await manager.cancel(job_id)
            except KeyError:
                continue
        record.updated_at = utc_now()
        store.update_creative_batch(record)
        return batch_projection(record)

    def compose_record(record: CreativeCompositionRecord) -> CreativeCompositionRecord:
        child_jobs = [store.get_job(job_id) for job_id in record.child_job_ids]
        child_asset_ids = [job.asset_ids[0] for job in child_jobs]
        request = JobRequest(
            operation="asset.pack",
            intent=f"Compose {record.layout.template}: {record.layout.title or 'untitled'}",
            inputs=[AssetInput(asset_id=asset_id) for asset_id in child_asset_ids],
            constraints={"layout_spec": record.layout.model_dump(mode="json")},
        )
        job = store.create_job(
            request,
            initial_status=JobStatus.RUNNING,
            initial_phase="compose",
        )
        root = contained(store.work_dir, store.work_dir / job.id)
        try:
            root.mkdir(mode=0o700)
            output = contained(root, root / "composed.png")
            font_path, font_sha256 = cache_composer_font(
                store.data_dir,
                str(record.layout_snapshot["font_sha256"])
                if "font_sha256" in record.layout_snapshot else None,
            )
            record.layout_snapshot = {**record.layout_snapshot, "font_sha256": font_sha256}
            store.update_creative_composition(record)
            deterministic_composer.compose(
                [store.asset_path(asset_id) for asset_id in child_asset_ids],
                record.layout,
                record.layout_snapshot,
                output,
                font_path=font_path,
            )
            width, height, validation = validate_png(output)
            digest = hashlib.sha256(output.read_bytes()).hexdigest()
            now = utc_now()
            asset_id = f"asset_{uuid.uuid4().hex}"
            provenance_id = f"prov_{uuid.uuid4().hex}"
            asset = Asset(
                id=asset_id,
                job_id=job.id,
                parent_asset_ids=child_asset_ids,
                mime_type="image/png",
                width=width,
                height=height,
                size_bytes=output.stat().st_size,
                sha256=digest,
                suggested_filename=f"media-forge-{record.layout.template}-{asset_id[6:14]}.png",
                provenance_id=provenance_id,
                created_at=now,
            )
            provenance = Provenance(
                id=provenance_id,
                asset_id=asset_id,
                parent_asset_ids=child_asset_ids,
                operation="asset.pack",
                intent=job.request.intent,
                model_id="media-forge/deterministic-composer",
                model_version="1.0.0",
                weights_hash="sha256:" + "0" * 64,
                license="derived-from-parent-assets",
                runtime_adapter="deterministic.pillow-composer",
                runtime_version=PILLOW_VERSION,
                tool_versions={"media-forge": __version__, "composer.layout": "1.0.0", "validator.png": "1.0.0"},
                seed=0,
                parameters={
                    "composition_id": record.id,
                    "layout": record.layout.model_dump(mode="json"),
                    "layout_snapshot": record.layout_snapshot,
                    "child_asset_ids": child_asset_ids,
                },
                reference_asset_hashes={asset_id: store.get_asset(asset_id).sha256 for asset_id in child_asset_ids},
                postprocessing=["composer.image_fit", "composer.frame", "composer.text", "png.normalize"],
                validation=validation,
                warnings=[],
                output_sha256=digest,
                created_at=now,
            )
            store.register_asset(asset, provenance, output)
            store.update_job(job.id, status=JobStatus.SUCCEEDED, progress=1, asset_ids=[asset.id])
            record.final_asset_ids.append(asset.id)
            record.composition_error = None
            record.updated_at = utc_now()
            return store.update_creative_composition(record)
        except Exception as exc:
            store.update_job(
                job.id,
                status=JobStatus.FAILED,
                progress=1,
                error=ErrorDetail(code="creative_composition_failed", message=str(exc)[:300]),
            )
            record.composition_error = {"code": "creative_composition_failed", "message": str(exc)[:300]}
            record.updated_at = utc_now()
            store.update_creative_composition(record)
            return record
        finally:
            if root.exists():
                shutil.rmtree(root)

    def composition_projection(record: CreativeCompositionRecord) -> dict[str, Any]:
        jobs = []
        for job_id in record.child_job_ids:
            try:
                jobs.append(store.get_job(job_id))
            except KeyError:
                continue
        statuses = [job.status.value for job in jobs]
        active = any(status in {"queued", "running"} for status in statuses)
        succeeded = sum(status == "succeeded" for status in statuses)
        failed = sum(status == "failed" for status in statuses) + len(record.submission_errors)
        canceled = sum(status == "canceled" for status in statuses)
        if (
            succeeded == record.layout.shot_count
            and not record.final_asset_ids
            and record.composition_error is None
        ):
            record = compose_record(record)
        if record.final_asset_ids:
            state = "succeeded"
        elif record.composition_error is not None:
            state = "failed"
        elif active:
            state = "running"
        elif succeeded:
            state = "partial"
        elif canceled and not failed:
            state = "canceled"
        else:
            state = "failed"
        completed = succeeded + failed + canceled
        return {
            **record.model_dump(mode="json"),
            "state": state,
            "completed_count": completed,
            "succeeded_count": succeeded,
            "failed_count": failed,
            "canceled_count": canceled,
            "progress": completed / record.layout.shot_count,
            "shot_asset_ids": [asset_id for job in jobs for asset_id in job.asset_ids[:1]],
            "asset_ids": list(record.final_asset_ids[-1:]),
            "children": [job.model_dump(mode="json") for job in jobs],
        }

    async def create_creative_composition(
        payload: dict[str, Any],
        submit_child: Callable[[JobRequest], Awaitable[dict[str, Any]]],
        identity: HostIdentity | None = None,
    ) -> dict[str, Any]:
        request = JobRequest.model_validate(payload.get("request"))
        creative_spec = CreativeSpec.model_validate(payload.get("creative_spec", {}))
        layout = LayoutSpec.model_validate(payload.get("layout"))
        profile_snapshot = manager.resolve_profiles(request)
        available_references = {item.asset_id for item in request.inputs} | set(
            profile_snapshot.get("reference_asset_ids", [])
        )
        capability_value = await capability_document(identity)
        director_mode = params_director_mode(payload)
        reference_context = accepted_reference_context(payload)
        directed = None
        if director_mode != "original":
            roles: list[ShotRole] = [
                value[0] for value in multi_cut_planner.SHOTS[:layout.shot_count]
            ]
            directed = await creative_director.shot_briefs(
                identity,
                request.intent,
                mode=director_mode,
                count=layout.shot_count,
                template=layout.template,
                roles=roles,
                reference_context=reference_context,
            )
        if directed is not None and directed.assistance_used:
            projected, _ = project_plan_to_creative_spec(
                directed.plan, creative_spec.model_dump(mode="json")
            )
            creative_spec = CreativeSpec.model_validate(projected)
        composition_id, child_requests, child_plans, layout_snapshot = multi_cut_planner.plan(
            request,
            creative_spec,
            layout,
            capabilities=capability_value["capabilities"],
            envelope=size_envelope(),
            available_reference_ids=available_references,
            director_plan=directed.plan if directed is not None and directed.assistance_used else None,
            shot_briefs=directed.shot_briefs if directed is not None and directed.assistance_used else None,
            reference_context=reference_context,
        )
        now = utc_now()
        record = store.create_creative_composition(CreativeCompositionRecord(
            id=composition_id,
            layout=layout,
            layout_snapshot=layout_snapshot,
            child_plans=child_plans,
            director=directed.model_dump(mode="json") if directed is not None else None,
            created_at=now,
            updated_at=now,
        ))
        for child in child_requests:
            try:
                submitted = await submit_child(child)
                record.child_job_ids.append(str(submitted["id"]))
            except (HTTPException, ProfileResolutionError, KeyError, ValueError) as exc:
                code = (
                    str(exc.detail.get("code", "composition_child_submission_failed"))
                    if isinstance(exc, HTTPException) and isinstance(exc.detail, dict)
                    else exc.code if isinstance(exc, ProfileResolutionError)
                    else "composition_child_submission_failed"
                )
                record.submission_errors.append({"code": code, "message": str(exc)[:300]})
            record.updated_at = utc_now()
            store.update_creative_composition(record)
        return composition_projection(record)

    def recompose_creative_composition(composition_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if set(payload) - {"composition_id", "title", "caption"}:
            raise ValueError("composition text update contains unsupported fields")
        record = store.get_creative_composition(composition_id)
        if not record.final_asset_ids:
            raise ValueError("composition is not ready")
        layout_value = record.layout.model_dump(mode="json") | {
            "title": payload.get("title", record.layout.title),
            "caption": payload.get("caption", record.layout.caption),
        }
        record.layout = LayoutSpec.model_validate(layout_value)
        previous_font = record.layout_snapshot.get("font_sha256")
        record.layout_snapshot = {
            **layout_catalog.resolve(record.layout),
            **({"font_sha256": previous_font} if previous_font else {}),
        }
        record.composition_error = None
        record.updated_at = utc_now()
        store.update_creative_composition(record)
        record = compose_record(record)
        if record.composition_error is not None:
            raise ValueError(record.composition_error["message"])
        return composition_projection(record)

    async def cancel_creative_composition(composition_id: str) -> dict[str, Any]:
        record = store.get_creative_composition(composition_id)
        for job_id in record.child_job_ids:
            try:
                job = store.get_job(job_id)
                if job.status.value not in {"succeeded", "failed", "canceled"}:
                    await manager.cancel(job_id)
            except KeyError:
                continue
        record.updated_at = utc_now()
        store.update_creative_composition(record)
        return composition_projection(record)

    async def evaluate_creative_candidates(
        payload: dict[str, Any], identity: HostIdentity | None = None
    ) -> dict[str, Any]:
        request = EvaluationRequest.model_validate(payload)
        if identity is None and isinstance(evaluator, HostCreativeEvaluator):
            raise CreativeEvaluationError(
                "host_ai_not_granted", "ControlDeck AI access is not granted"
            )
        if (
            identity is not None
            and "ai.inference" not in identity.granted_capabilities
            and isinstance(evaluator, HostCreativeEvaluator)
        ):
            raise CreativeEvaluationError(
                "host_ai_not_granted", "ControlDeck AI access is not granted"
            )
        if not await evaluator.available(identity):
            raise CreativeEvaluationError(
                "vision_analyzer_unavailable", "ControlDeck vision analyzer is unavailable"
            )
        reference_paths = tuple(store.asset_path(asset_id) for asset_id in request.reference_asset_ids)
        results = []
        for asset_id in request.asset_ids:
            asset = store.get_asset(asset_id)
            if not asset.mime_type.startswith("image/"):
                raise ValueError("creative evaluation accepts image assets only")
            evaluated = await evaluator.evaluate(
                store.asset_path(asset_id),
                request.intent,
                creative_plan=request.creative_plan,
                reference_paths=reference_paths,
                identity=identity,
            )
            evaluation = evaluated.result.model_dump(mode="json")
            results.append({
                "asset_id": asset_id,
                "evaluation": evaluation,
                "scores": evaluation["scores"],
                "rank_score": evaluated.rank_score,
                "summary": evaluated.summary,
                "evaluator": evaluated.evaluator,
                "relevant_dimensions": list(evaluated.relevant_dimensions),
            })
        results.sort(key=lambda item: (-item["rank_score"], item["asset_id"]))
        return {
            "results": results,
            "ranked_asset_ids": [item["asset_id"] for item in results],
            "advisory": True,
            "regeneration_requested": False,
        }

    @app.get("/api/v1/capabilities")
    async def capabilities() -> dict[str, Any]:
        return await capability_document()

    @app.get("/api/v1/models")
    async def models() -> dict[str, Any]:
        return model_catalog()

    @app.post("/api/v1/jobs", status_code=202)
    async def create_job(job_request: JobRequest, response: Response) -> dict[str, Any]:
        try:
            job_request = apply_asset_brief(job_request)
        except AssetBriefError as exc:
            raise HTTPException(
                status_code=422, detail={"code": exc.code, "message": str(exc)[:300]}
            ) from exc
        try:
            job = manager.submit(job_request)
        except ProfileResolutionError as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code}) from exc
        response.headers["Location"] = f"/api/v1/jobs/{job.id}"
        return job.model_dump(mode="json")

    @app.get("/api/v1/jobs")
    async def list_jobs(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
        return {"items": [item.model_dump(mode="json") for item in store.list_jobs(limit)]}

    @app.get("/api/v1/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, Any]:
        try:
            return store.get_job(job_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "job_not_found"}) from exc

    @app.delete("/api/v1/jobs/{job_id}")
    async def cancel_job(job_id: str) -> dict[str, Any]:
        try:
            await manager.cancel(job_id)
            return store.get_job(job_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "job_not_found"}) from exc

    @app.get("/api/v1/assets")
    async def list_assets(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
        return {"items": [item.model_dump(mode="json") for item in store.list_assets(limit)]}

    @app.post("/workspace-api/assets/{asset_id}/thumbnail", include_in_schema=False)
    async def standalone_asset_thumbnail(asset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            asset = store.get_asset(asset_id)
            if asset.mime_type == "model/gltf-binary":
                thumbnail = thumbnails.model_cached(
                    store.thumbnail_dir, asset_id, thumbnails.clamp_max_side(payload.get("max_side"))
                )
            elif not thumbnails.is_thumbnailable(asset.mime_type):
                raise ThumbnailError()
            else:
                thumbnail = thumbnails.cached(
                    store.asset_path(asset_id),
                    store.thumbnail_dir,
                    asset_id,
                    thumbnails.clamp_max_side(payload.get("max_side")),
                    asset.mime_type,
                )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "asset_not_found"}) from exc
        except (ThumbnailError, OSError) as exc:
            raise HTTPException(status_code=422, detail={"code": "thumbnail_unavailable"}) from exc
        return {
            "mime_type": thumbnail.mime_type,
            "width": thumbnail.width,
            "height": thumbnail.height,
            "base64": base64.b64encode(thumbnail.content).decode("ascii"),
        }

    def save_model_thumbnail(asset_id: str, encoded: object) -> dict[str, Any]:
        try:
            asset = store.get_asset(asset_id)
        except KeyError as exc:
            raise ModelViewerError("model_viewer_not_found", "3D model asset is unavailable") from exc
        if asset.mime_type != "model/gltf-binary":
            raise ModelViewerError(
                "model_viewer_unsupported", "thumbnail target is not a raw GLB model"
            )
        if not isinstance(encoded, str) or len(encoded) > 360_000:
            raise ModelViewerError("model_thumbnail_invalid", "model thumbnail exceeds its bound")
        try:
            content = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise ModelViewerError("model_thumbnail_invalid", "model thumbnail is invalid") from exc
        captured = thumbnails.store_model_capture(store.thumbnail_dir, asset_id, content)
        return {
            "asset_id": asset_id,
            "mime_type": captured.mime_type,
            "width": captured.width,
            "height": captured.height,
            "size_bytes": len(captured.content),
        }

    @app.post("/workspace-api/assets/{asset_id}/model/open", include_in_schema=False)
    async def standalone_model_open(asset_id: str) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(standalone_model_viewer.open, asset_id)
        except ModelViewerError as exc:
            raise HTTPException(
                status_code=422, detail={"code": exc.code, "message": str(exc)[:300]}
            ) from exc

    @app.post("/workspace-api/models/{handle}/bytes", include_in_schema=False)
    async def standalone_model_bytes(handle: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(
                standalone_model_viewer.read,
                handle,
                payload.get("offset", 0),
                payload.get("length", 512 * 1024),
            )
        except ModelViewerError as exc:
            raise HTTPException(
                status_code=422, detail={"code": exc.code, "message": str(exc)[:300]}
            ) from exc

    @app.post("/workspace-api/models/{handle}/close", include_in_schema=False)
    async def standalone_model_close(handle: str) -> dict[str, Any]:
        return {"closed": await asyncio.to_thread(standalone_model_viewer.close, handle)}

    @app.post("/workspace-api/assets/{asset_id}/model/thumbnail", include_in_schema=False)
    async def standalone_model_thumbnail(asset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(save_model_thumbnail, asset_id, payload.get("base64"))
        except (ModelViewerError, ThumbnailError) as exc:
            code = getattr(exc, "code", "model_thumbnail_invalid")
            raise HTTPException(
                status_code=422, detail={"code": code, "message": str(exc)[:300]}
            ) from exc

    @app.post("/workspace-api/library", include_in_schema=False)
    async def standalone_library(payload: dict[str, Any]) -> dict[str, Any]:
        kind = str(payload.get("kind", "all"))
        if kind not in library.KINDS:
            raise HTTPException(status_code=422, detail={"code": "workspace_request_rejected"})
        media_kind = str(payload.get("media_kind", "all"))
        if media_kind not in library.MEDIA_KINDS:
            raise HTTPException(status_code=422, detail={"code": "workspace_request_rejected"})
        limit = library.clamp_limit(payload.get("limit"))
        before = payload.get("before")
        if before is not None and not isinstance(before, str):
            raise HTTPException(status_code=422, detail={"code": "workspace_request_rejected"})
        records = store.list_asset_records(limit, before)
        return library.page(
            records,
            kind=kind,
            include_masks=payload.get("include_masks") is True,
            limit=limit,
            media_kind=media_kind,
            thumbnail=grid_thumbnail,
        )

    @app.get("/api/v1/reference-collections")
    async def list_reference_collections() -> dict[str, Any]:
        return {"items": [item.model_dump(mode="json") for item in store.list_reference_collections()]}

    @app.post("/api/v1/reference-collections", status_code=201)
    async def create_reference_collection(value: ReferenceCollectionInput) -> dict[str, Any]:
        try:
            return store.create_reference_collection(value).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=422, detail={"code": "reference_asset_not_found"}) from exc

    @app.delete("/api/v1/reference-collections/{collection_id}", status_code=204)
    async def delete_reference_collection(collection_id: str) -> Response:
        try:
            store.delete_reference_collection(collection_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "reference_collection_not_found"}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail={"code": "reference_collection_in_use"}) from exc
        return Response(status_code=204)

    @app.get("/api/v1/profiles")
    async def list_profiles() -> dict[str, Any]:
        return {"items": [item.model_dump(mode="json") for item in store.list_profiles()]}

    @app.get("/api/v1/domain-profiles")
    async def list_domain_profiles() -> dict[str, Any]:
        return {"items": m5_profile_documents()}

    @app.post("/api/v1/profiles", status_code=201)
    async def create_profile(value: ProfileInput) -> dict[str, Any]:
        try:
            return store.create_profile(value).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=422, detail={"code": "reference_collection_not_found"}) from exc

    @app.delete("/api/v1/profiles/{profile_id}", status_code=204)
    async def delete_profile(profile_id: str) -> Response:
        try:
            store.delete_profile(profile_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "profile_not_found"}) from exc
        return Response(status_code=204)

    @app.post("/api/v1/assets/import", status_code=201)
    async def import_asset(
        request: Request,
        purpose: Literal["source", "edit_mask"] = Query(default="source"),
    ) -> dict[str, Any]:
        media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        # 動画は画像と別の上限を持つ。共通の 64 MiB で切ると、実測した 15 秒の
        # clip（17.2 MB）は通っても、少し大きいものが理由なく弾かれる。
        limit = MAX_VIDEO_IMPORT_BYTES if media_type in VIDEO_MEDIA_TYPES else MAX_IMPORT_BYTES
        content = bytearray()
        async for chunk in request.stream():
            if len(content) + len(chunk) > limit:
                raise HTTPException(status_code=413, detail={"code": "asset_import_too_large"})
            content.extend(chunk)
        try:
            return import_asset_bytes(
                store,
                bytes(content),
                purpose=purpose,
                media_type=media_type,
            ).model_dump(mode="json")
        except AssetImportError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": (
                        "invalid_glb_import" if media_type == "model/gltf-binary"
                        else "invalid_video_import" if media_type in VIDEO_MEDIA_TYPES
                        else "invalid_image_import"
                    ),
                    "message": str(exc)[:300],
                },
            ) from exc

    @app.get("/api/v1/assets/{asset_id}")
    async def get_asset(asset_id: str) -> dict[str, Any]:
        try:
            return store.get_asset(asset_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "asset_not_found"}) from exc

    @app.get("/api/v1/assets/{asset_id}/content")
    async def asset_content(asset_id: str) -> FileResponse:
        try:
            asset = store.get_asset(asset_id)
            return FileResponse(
                store.asset_path(asset_id),
                media_type=asset.mime_type,
                filename=asset.suggested_filename,
                content_disposition_type="inline",
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "asset_not_found"}) from exc

    @app.get("/api/v1/assets/{asset_id}/provenance")
    async def asset_provenance(asset_id: str) -> dict[str, Any]:
        try:
            return store.get_provenance(asset_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "asset_not_found"}) from exc

    @app.get("/schemas/{schema_name}")
    async def schema(schema_name: str) -> FileResponse:
        allowed = {item.name for item in SCHEMAS_DIR.glob("*.json")}
        if schema_name not in allowed:
            raise HTTPException(status_code=404, detail={"code": "schema_not_found"})
        return FileResponse(SCHEMAS_DIR / schema_name, media_type="application/schema+json")

    @app.post("/addon/v1/commands/create")
    async def create_command(request: Request) -> dict[str, Any]:
        await authorize_host(request)
        return {"route": "/x/media-forge/workspace/create"}

    @app.post("/addon/v1/workflow/execute")
    async def workflow_execute(request: Request) -> dict[str, Any]:
        identity = await authorize_host(request)
        payload = await request.json()
        value = host_job_input(payload)
        return submitted_reference(await submit_hosted(value, identity, workload_class="workflow"))

    @app.post("/addon/v1/workflow/media.generate/execute")
    async def workflow_execute_compat(request: Request) -> dict[str, Any]:
        return await workflow_execute(request)

    @app.post("/addon/v1/workflow/media.generate/cancel")
    async def workflow_cancel(request: Request) -> dict[str, Any]:
        await authorize_host(request)
        payload = await request.json()
        reject_host_paths(payload)
        job_id = payload.get("job_id")
        if not isinstance(job_id, str):
            raise HTTPException(status_code=422, detail={"code": "invalid_job_id"})
        try:
            job = await manager.cancel(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "job_not_found"}) from exc
        return submitted_reference(job.model_dump(mode="json"))

    @app.post("/addon/v1/agent/capabilities")
    async def agent_capabilities(request: Request) -> dict[str, Any]:
        identity = await authorize_host(request)
        payload = await request.json()
        reject_host_paths(payload)
        return await capability_document(identity)

    @app.post("/addon/v1/agent/generate")
    async def agent_generate(request: Request) -> dict[str, Any]:
        identity = await authorize_host(request)
        payload = await request.json()
        value = host_job_input(payload)
        job = await submit_hosted(value, identity, workload_class="agent-interactive")
        terminal = await wait_for_terminal(job["id"])
        await manager.wait_cleanup(job["id"])
        if terminal["status"] != "succeeded":
            error = terminal.get("error") or {"code": "media_job_failed"}
            raise HTTPException(status_code=502, detail={"code": error.get("code", "media_job_failed")})
        result = submitted_reference(terminal)
        result["asset_id"] = terminal["asset_ids"][0] if terminal["asset_ids"] else None
        return result

    @app.post("/addon/v1/agent/inspect")
    async def agent_inspect(request: Request) -> dict[str, Any]:
        await authorize_host(request)
        payload = await request.json()
        reject_host_paths(payload)
        asset_id = payload.get("input", {}).get("asset_id")
        if not isinstance(asset_id, str):
            raise HTTPException(status_code=422, detail={"code": "invalid_asset_id"})
        try:
            asset = store.get_asset(asset_id)
            provenance = store.get_provenance(asset_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "asset_not_found"}) from exc
        return {
            "asset": asset.model_dump(mode="json"),
            "provenance": {
                "operation": provenance.operation,
                "license": provenance.license,
                "parent_asset_ids": provenance.parent_asset_ids,
                "validation": provenance.validation,
                "warnings": provenance.warnings,
                "output_sha256": provenance.output_sha256,
            },
        }

    @app.post("/addon/v1/agent/pack")
    async def agent_pack(request: Request) -> dict[str, Any]:
        identity = await authorize_host(request)
        payload = await request.json()
        reject_host_paths(payload)
        if "files.export" not in identity.granted_capabilities:
            raise HTTPException(status_code=403, detail={"code": "host_capability_not_granted"})
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail={"code": "invalid_execution_envelope"})
        request_input = payload.get("input", {})
        manifest = placement_manifest(request_input)
        correlation = payload.get("correlation")
        host_job_id = correlation.get("job_id") if isinstance(correlation, dict) else None
        if not isinstance(host_job_id, str) or identity.subject != f"job:{host_job_id}":
            raise HTTPException(status_code=403, detail={"code": "host_job_scope_mismatch"})
        # 1 バイトも書く前に全件を確定させる。3 件書いたあとで重複名や欠落資産に
        # 気づいても、Host の commit は取り消せない。
        try:
            planned = plan_placements(manifest, store.get_asset)
        except PlacementPlanError as exc:
            status = 404 if exc.code == "asset_not_found" else 422
            raise HTTPException(
                status_code=status, detail={"code": exc.code, "message": str(exc)[:300]}
            ) from exc

        grant_id = require_grant_id(manifest.output_grant_id)
        receipts: list[PlacementReceipt] = []
        failure: HTTPException | None = None
        for entry in planned:
            if failure is not None:
                # 失敗のあとは書き続けない。頼まれた仕事の残りは未着手と報告する。
                receipts.append(PlacementReceipt(
                    committed=False,
                    source_asset_id=entry.item.asset_id,
                    filename=entry.filename,
                    media_type=entry.mime_type,
                    sha256=entry.sha256,
                    size_bytes=entry.size_bytes,
                    width=entry.width,
                    height=entry.height,
                    role=entry.item.role,
                    error={"code": "not_attempted", "message": "an earlier item failed"},
                ))
                continue
            try:
                committed = await commit_file(
                    host,
                    identity,
                    host_job_id=host_job_id,
                    grant_id=grant_id,
                    source=store.asset_path(entry.item.asset_id),
                    filename=entry.filename,
                    mime_type=entry.mime_type,
                    sha256=entry.sha256,
                )
                project_asset_id = committed.get("asset_id")
                if not isinstance(project_asset_id, str) or not project_asset_id.startswith("asset:"):
                    raise HostApiError("invalid_host_response", "ControlDeck returned an invalid output", 502)
            except HostApiError as exc:
                failure = HTTPException(status_code=exc.status_code, detail={"code": exc.code})
                receipts.append(PlacementReceipt(
                    committed=False,
                    source_asset_id=entry.item.asset_id,
                    filename=entry.filename,
                    media_type=entry.mime_type,
                    sha256=entry.sha256,
                    size_bytes=entry.size_bytes,
                    width=entry.width,
                    height=entry.height,
                    role=entry.item.role,
                    error={"code": exc.code, "message": str(exc)[:300]},
                ))
                continue
            except (OSError, ValueError, KeyError) as exc:
                failure = HTTPException(
                    status_code=422, detail={"code": "asset_placement_rejected"}
                )
                receipts.append(PlacementReceipt(
                    committed=False,
                    source_asset_id=entry.item.asset_id,
                    filename=entry.filename,
                    media_type=entry.mime_type,
                    sha256=entry.sha256,
                    size_bytes=entry.size_bytes,
                    width=entry.width,
                    height=entry.height,
                    role=entry.item.role,
                    error={"code": "asset_placement_rejected", "message": str(exc)[:300]},
                ))
                continue
            receipts.append(PlacementReceipt(
                committed=True,
                source_asset_id=entry.item.asset_id,
                filename=entry.filename,
                media_type=entry.mime_type,
                sha256=entry.sha256,
                size_bytes=entry.size_bytes,
                host_asset_id=project_asset_id,
                width=entry.width,
                height=entry.height,
                role=entry.item.role,
            ))

        if failure is not None and not any(item.committed for item in receipts):
            raise failure
        return placement_response(request_input, receipts, partial=failure is not None)

    @app.post("/addon/v1/context/edit-image")
    async def context_edit_image(request: Request) -> dict[str, Any]:
        identity = await authorize_host(request)
        payload = await request.json()
        reject_host_paths(payload)
        context = payload.get("context")
        if not isinstance(context, dict) or context.get("type") not in {"file", "project"}:
            raise HTTPException(status_code=422, detail={"code": "invalid_context"})
        resource_id = context.get("resource_id")
        grant_id = context.get("grant_id")
        source: dict[str, Any] | None = None
        if context["type"] == "file":
            if (
                not isinstance(resource_id, str)
                or not isinstance(grant_id, str)
                or resource_id != grant_id
            ):
                raise HTTPException(status_code=422, detail={"code": "scoped_grant_required"})
            try:
                metadata, content = await read_grant(
                    host,
                    identity,
                    require_grant_id(grant_id),
                    max_bytes=MAX_CONTEXT_IMAGE_BYTES,
                )
            except GrantContentTooLarge as exc:
                raise HTTPException(status_code=413, detail={"code": "context_image_too_large"}) from exc
            except (HostApiError, ValueError) as exc:
                status_code = exc.status_code if isinstance(exc, HostApiError) else 422
                code = exc.code if isinstance(exc, HostApiError) else "invalid_scoped_grant"
                raise HTTPException(status_code=status_code, detail={"code": code}) from exc
            try:
                with Image.open(BytesIO(content)) as image:
                    image.verify()
                with Image.open(BytesIO(content)) as image:
                    width, height = image.size
                    image_format = image.format
                    mode = image.mode
            except (UnidentifiedImageError, OSError, SyntaxError) as exc:
                raise HTTPException(status_code=422, detail={"code": "invalid_context_image"}) from exc
            if (
                image_format not in {"PNG", "JPEG"}
                or width <= 0
                or height <= 0
                or width * height > MAX_CONTEXT_IMAGE_PIXELS
            ):
                raise HTTPException(status_code=422, detail={"code": "unsupported_context_image"})
            source = {
                "name": metadata.get("name", "selected"),
                "size": len(content),
                "width": width,
                "height": height,
                "mode": mode,
            }
        elif not isinstance(resource_id, str) or not resource_id:
            raise HTTPException(status_code=422, detail={"code": "invalid_context"})
        return {
            "action": "open_route",
            "route": "/x/media-forge/workspace/create",
            "context": {"type": context["type"], "source": source},
        }

    async def push_job_events(websocket: WebSocket, subscription: JobSubscription) -> None:
        """Coalesce job changes so fine-grained progress cannot flood the socket."""
        pending: dict[str, Any] = {}
        while True:
            job = await subscription.queue.get()
            pending[job.id] = job
            await asyncio.sleep(JOB_EVENT_INTERVAL_SEC)
            while not subscription.queue.empty():
                queued = subscription.queue.get_nowait()
                pending[queued.id] = queued
            for job_id, value in list(pending.items()):
                try:
                    await websocket.send_json({
                        "type": "event",
                        "event": "job.changed",
                        "data": value.model_dump(mode="json"),
                    })
                except (WebSocketDisconnect, RuntimeError):
                    return
                if value.status.value in TERMINAL_JOB_STATES:
                    subscription.unwatch([job_id])
            pending.clear()

    async def push_session_events(
        websocket: WebSocket, subscription: SessionSubscription
    ) -> None:
        """Coalesce session invalidations so a batch cannot flood the socket.

        The payload carries only which parts went stale. The workspace re-reads
        those parts, so no projection has to be duplicated into an event.
        """
        while True:
            part = await subscription.queue.get()
            stale = {part}
            await asyncio.sleep(JOB_EVENT_INTERVAL_SEC)
            while not subscription.queue.empty():
                stale.add(subscription.queue.get_nowait())
            try:
                await websocket.send_json({
                    "type": "event",
                    "event": "session.changed",
                    "data": {"parts": sorted(stale)},
                })
            except (WebSocketDisconnect, RuntimeError):
                return

    async def push_model_operation_events(
        websocket: WebSocket,
        subscription: ModelOperationSubscription,
    ) -> None:
        while True:
            operation = await subscription.queue.get()
            try:
                await websocket.send_json({
                    "type": "event",
                    "event": "model.operation.changed",
                    "data": operation.model_dump(mode="json"),
                })
            except (WebSocketDisconnect, RuntimeError):
                return
            if operation.state in TERMINAL_MODEL_OPERATION_STATES:
                subscription.unwatch([operation.id])

    def grid_thumbnail(asset: Asset) -> dict[str, Any] | None:
        """一覧カード用の小さな版。1 枚でも失敗したら None を返して一覧は続ける。"""
        if asset.mime_type == "model/gltf-binary":
            try:
                rendered = thumbnails.model_cached(
                    store.thumbnail_dir, asset.id, library.GRID_THUMBNAIL_MAX_SIDE
                )
            except (ThumbnailError, KeyError, OSError):
                return None
        elif not thumbnails.is_thumbnailable(asset.mime_type):
            return None
        else:
            try:
                rendered = thumbnails.cached(
                    store.asset_path(asset.id),
                    store.thumbnail_dir,
                    asset.id,
                    library.GRID_THUMBNAIL_MAX_SIDE,
                    asset.mime_type,
                )
            except (ThumbnailError, KeyError, OSError):
                return None
        return {
            "mime_type": rendered.mime_type,
            "width": rendered.width,
            "height": rendered.height,
            "base64": base64.b64encode(rendered.content).decode("ascii"),
        }

    SESSION_PARTS: tuple[str, ...] = (
        "preferences",
        "capabilities",
        "profiles",
        "reference_collections",
        "domain_profiles",
        "models",
        "model_catalog",
        "model_operations",
        "blender_runtime",
        "blender_sessions",
        "scenes",
        "library",
        "creative_batches",
        "creative_compositions",
        "jobs",
    )

    def blender_runtime_part() -> dict[str, Any]:
        try:
            catalog = blender_runtime_operations.catalog()
            management = {"management_available": True, "catalog": catalog}
        except BlenderRuntimeOperationError as exc:
            management = {
                "management_available": False,
                "management_reason": exc.code,
                "catalog": None,
            }
        runtime_status = blender_runtimes.status()
        web_status = blender_runtime_operations.web_status()
        fingerprint = hashlib.sha256(json.dumps({
            "runtime": blender_runtimes.fingerprint(),
            "web": web_status.get("fingerprint"),
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return {
            **runtime_status,
            "web_pack": web_status,
            "fingerprint": fingerprint,
            **management,
            "operations": [
                item.model_dump(mode="json")
                for item in store.list_blender_runtime_operations()
            ],
        }

    async def session_snapshot(
        identity: HostIdentity | None, parts: tuple[str, ...]
    ) -> dict[str, Any]:
        """Compose the whole workspace state on the server in one pass.

        The workspace used to derive its own state from ten sequential requests
        during boot. State ownership now lives here: the client renders whatever
        this returns and re-reads only the parts a session event invalidates.

        Every part fails soft on its own. One unavailable part (a Host AI probe,
        an absent model catalog) must not cost the caller the whole session.
        """
        wanted = set(parts)
        snapshot: dict[str, Any] = {"session_version": 1, "parts": sorted(wanted)}
        # 画面を開くたびに帳尻を合わせる。埋め込みの boot はここを通り、
        # 個別の models.list は呼ばない。再起動で消えた評価をここで拾う。
        if identity is not None and "models" in wanted:
            start_pending_lora_base_evaluations(identity)

        async def capabilities_part() -> dict[str, Any]:
            envelope = size_envelope()
            return {
                **await capability_document(identity),
                "envelope": envelope,
                "presets": size_presets(envelope),
                "device": {"vram_bytes": device_vram_bytes()},
            }

        def preferences_part() -> dict[str, Any]:
            return {"values": preferences.merged(
                store.get_preferences(preferences.subject_of(identity))
            )}

        def model_catalog_part() -> dict[str, Any]:
            if model_operations is None:
                return {"items": [], "management_available": False}
            value = model_operations.catalog()
            value["evaluation"] = {
                "available_model_ids": model_evaluations.available_model_ids()
                if model_evaluations is not None else []
            }
            return value

        def library_part() -> dict[str, Any]:
            limit = library.clamp_limit(SESSION_RECENT_LIMIT)
            return library.page(
                store.list_asset_records(limit, None),
                kind="all",
                include_masks=False,
                limit=limit,
                thumbnail=grid_thumbnail,
            )

        producers: dict[str, Any] = {
            "preferences": preferences_part,
            "capabilities": capabilities_part,
            "profiles": lambda: {"items": [
                item.model_dump(mode="json") for item in store.list_profiles()
            ]},
            "reference_collections": lambda: {"items": [
                item.model_dump(mode="json") for item in store.list_reference_collections()
            ]},
            "domain_profiles": lambda: {"items": m5_profile_documents()},
            "models": model_catalog,
            "model_catalog": model_catalog_part,
            "model_operations": lambda: {"items": [
                item.model_dump(mode="json") for item in store.list_model_operations()
            ]},
            "blender_runtime": blender_runtime_part,
            "blender_sessions": lambda: blender_sessions.list(preferences.subject_of(identity)),
            "scenes": lambda: {
                "items": [
                    item.model_dump(mode="json")
                    for item in scenes.list(preferences.subject_of(identity))
                ],
                "working_copies": [
                    item.model_dump(mode="json")
                    for item in scene_workspace.list_working_copies(
                        preferences.subject_of(identity)
                    )
                ],
            },
            "library": library_part,
            "creative_batches": lambda: {"items": [
                batch_projection(item) for item in store.list_creative_batches()
            ]},
            "creative_compositions": lambda: {"items": [
                composition_projection(item) for item in store.list_creative_compositions()
            ]},
            "jobs": lambda: {"items": [
                item.model_dump(mode="json") for item in store.list_jobs(SESSION_JOB_LIMIT)
            ]},
        }

        async def produce(name: str) -> tuple[str, dict[str, Any]]:
            try:
                value = producers[name]()
                if inspect.isawaitable(value):
                    value = await value
                return name, value
            except Exception as exc:  # noqa: BLE001 - 1 部分の失敗で session 全体を失わせない
                logger.warning("session part %s is unavailable: %s", name, exc)
                return name, {"unavailable": True, "code": _error_code(exc)}

        for name, value in await asyncio.gather(
            *(produce(name) for name in SESSION_PARTS if name in wanted)
        ):
            snapshot[name] = value
        return snapshot

    def requested_session_parts(params: dict[str, Any]) -> tuple[str, ...]:
        raw = params.get("parts")
        if raw is None:
            return SESSION_PARTS
        if not isinstance(raw, list) or not all(isinstance(value, str) for value in raw):
            raise ValueError("session parts must be a list of strings")
        wanted = tuple(value for value in SESSION_PARTS if value in set(raw))
        if not wanted:
            raise ValueError("session parts must name at least one known part")
        return wanted

    @app.websocket("/ws")
    async def workspace_socket(websocket: WebSocket) -> None:
        try:
            identity = await require_host_service_headers(websocket.headers, host)
        except HTTPException:
            await websocket.close(code=4401, reason="invalid host service token")
            return
        await websocket.accept()
        uploads: dict[str, dict[str, Any]] = {}
        scene_upload_ids: set[str] = set()
        model_viewer = ModelViewerSession(store)
        scene_backups = SceneBackupSession(store)
        subscription = events.subscribe(asyncio.get_running_loop())
        sender = asyncio.create_task(push_job_events(websocket, subscription))
        model_subscription = model_events.subscribe(asyncio.get_running_loop())
        model_sender = asyncio.create_task(push_model_operation_events(websocket, model_subscription))
        session_subscription = session_events.subscribe(asyncio.get_running_loop())
        session_sender = asyncio.create_task(push_session_events(websocket, session_subscription))
        try:
            while True:
                raw = await websocket.receive_text()
                if len(raw.encode()) > 1024 * 1024:
                    await websocket.close(code=4409, reason="request too large")
                    return
                request_id = ""
                try:
                    payload = json.loads(raw)
                    if not isinstance(payload, dict):
                        raise ValueError("request must be an object")
                    request_id = str(payload.get("id", ""))[:128]
                    method = payload.get("method")
                    params = payload.get("params", {})
                    if not request_id or not isinstance(method, str) or not isinstance(params, dict):
                        raise ValueError("invalid workspace request")
                    reject_host_paths(params)
                    result: dict[str, Any]
                    if method == "jobs.create":
                        value = JobRequest.model_validate(params)
                        result = await submit_hosted(value, identity, workload_class="interactive")
                    elif method == "jobs.get":
                        result = store.get_job(str(params.get("job_id", ""))).model_dump(mode="json")
                    elif method == "jobs.cancel":
                        result = (await manager.cancel(str(params.get("job_id", "")))).model_dump(mode="json")
                    elif method == "jobs.list":
                        result = {"items": [item.model_dump(mode="json") for item in store.list_jobs(100)]}
                    elif method == "jobs.clear":
                        result = {"cleared": store.clear_finished_jobs()}
                    elif method == "assets.list":
                        result = {"items": [item.model_dump(mode="json") for item in store.list_assets(100)]}
                    elif method == "assets.import":
                        encoded = params.get("base64")
                        purpose = params.get("purpose", "source")
                        media_type = params.get("media_type")
                        if media_type is not None and (
                            not isinstance(media_type, str)
                            or media_type not in {
                                "application/octet-stream", "image/png", "image/jpeg", "model/gltf-binary"
                            }
                        ):
                            raise ValueError("asset import media type is invalid")
                        if not isinstance(encoded, str) or len(encoded) > (MAX_IMPORT_BYTES * 4 // 3 + 8):
                            raise ValueError("asset import payload exceeds the transport bound")
                        try:
                            content = base64.b64decode(encoded, validate=True)
                        except ValueError as exc:
                            raise ValueError("asset import payload is not valid base64") from exc
                        result = import_asset_bytes(
                            store,
                            content,
                            purpose=str(purpose),
                            media_type=media_type if isinstance(media_type, str) else None,
                        ).model_dump(mode="json")
                    elif method == "assets.import_grant":
                        if identity is None:
                            raise ValueError("Host identity is required for scoped import")
                        if params.get("purpose") != "source" or params.get("media_type") != "model/gltf-binary":
                            raise ValueError("scoped import accepts a source GLB only")
                        metadata, content = await read_grant(
                            host,
                            identity,
                            require_grant_id(str(params.get("grant_id", ""))),
                            max_bytes=MAX_IMPORT_BYTES,
                        )
                        result = import_asset_bytes(
                            store,
                            content,
                            purpose="source",
                            media_type="model/gltf-binary",
                        ).model_dump(mode="json")
                        result["source_name"] = str(metadata.get("name", ""))[:255]
                    elif method == "assets.import.begin":
                        size = params.get("size")
                        purpose = params.get("purpose")
                        media_type = params.get("media_type")
                        if (
                            not isinstance(size, int)
                            or isinstance(size, bool)
                            or not 1 <= size <= MAX_IMPORT_BYTES
                            or purpose not in {"source", "edit_mask"}
                            or (media_type == "model/gltf-binary" and purpose != "source")
                            or (
                                media_type is not None
                                and (
                                    not isinstance(media_type, str)
                                    or media_type not in {
                                        "application/octet-stream", "image/png", "image/jpeg", "model/gltf-binary"
                                    }
                                )
                            )
                            or len(uploads) >= 2
                        ):
                            raise ValueError("asset import declaration is invalid")
                        upload_id = f"upload_{uuid.uuid4().hex}"
                        root = contained(store.work_dir, store.work_dir / f"workspace-{upload_id}")
                        root.mkdir(mode=0o700)
                        path = contained(root, root / "content.bin")
                        path.touch(mode=0o600)
                        uploads[upload_id] = {
                            "path": path,
                            "root": root,
                            "size": size,
                            "received": 0,
                            "purpose": purpose,
                            "media_type": media_type,
                        }
                        result = {"upload_id": upload_id, "chunk_bytes": 512 * 1024}
                    elif method == "assets.import.chunk":
                        upload_id = params.get("upload_id")
                        offset = params.get("offset")
                        encoded = params.get("base64")
                        upload = uploads.get(upload_id) if isinstance(upload_id, str) else None
                        if (
                            upload is None
                            or not isinstance(offset, int)
                            or isinstance(offset, bool)
                            or offset != upload["received"]
                            or not isinstance(encoded, str)
                            or len(encoded) > 700_000
                        ):
                            raise ValueError("asset import chunk is invalid")
                        try:
                            chunk = base64.b64decode(encoded, validate=True)
                        except ValueError as exc:
                            raise ValueError("asset import chunk is not valid base64") from exc
                        if not chunk or len(chunk) > 512 * 1024 or upload["received"] + len(chunk) > upload["size"]:
                            raise ValueError("asset import chunk exceeds its declaration")
                        with upload["path"].open("ab") as stream:
                            stream.write(chunk)
                        upload["received"] += len(chunk)
                        result = {"received": upload["received"]}
                    elif method == "assets.import.commit":
                        upload_id = params.get("upload_id")
                        upload = uploads.get(upload_id) if isinstance(upload_id, str) else None
                        if upload is None or upload["received"] != upload["size"]:
                            raise ValueError("asset import is incomplete")
                        uploads.pop(upload_id)
                        try:
                            content = upload["path"].read_bytes()
                            result = import_asset_bytes(
                                store,
                                content,
                                purpose=upload["purpose"],
                                media_type=upload["media_type"],
                            ).model_dump(mode="json")
                        finally:
                            shutil.rmtree(upload["root"])
                    elif method == "assets.provenance":
                        result = store.get_provenance(str(params.get("asset_id", ""))).model_dump(mode="json")
                    elif method == "assets.model.open":
                        if set(params) != {"asset_id"}:
                            raise ValueError("model viewer open accepts only asset_id")
                        result = await asyncio.to_thread(
                            model_viewer.open, str(params.get("asset_id", ""))
                        )
                    elif method == "assets.model.bytes":
                        if not {"handle", "offset"} <= set(params) or set(params) - {
                            "handle", "offset", "length"
                        }:
                            raise ValueError("model viewer bytes accepts handle, offset, and length")
                        result = await asyncio.to_thread(
                            model_viewer.read,
                            str(params.get("handle", "")),
                            params.get("offset"),
                            params.get("length", 512 * 1024),
                        )
                    elif method == "assets.model.close":
                        if set(params) != {"handle"}:
                            raise ValueError("model viewer close accepts only handle")
                        result = {"closed": await asyncio.to_thread(
                            model_viewer.close, str(params.get("handle", ""))
                        )}
                    elif method == "assets.model.thumbnail":
                        if set(params) != {"asset_id", "base64"}:
                            raise ValueError("model thumbnail accepts asset_id and base64")
                        result = await asyncio.to_thread(
                            save_model_thumbnail,
                            str(params.get("asset_id", "")),
                            params.get("base64"),
                        )
                    elif method == "assets.content":
                        # 原寸で預かった写真は転送上限を超える（実測: 12.2MP の
                        # 写真が PNG で 13.6MiB）。断ると「透かしは消せたが見られ
                        # ない」になるので、見るためだけの縮小版を返し、縮めたこと
                        # を言う。原寸は保存で取り出せる（export は host へファイル
                        # のまま渡すので、この上限に縛られない）。
                        asset_id = str(params.get("asset_id", ""))
                        asset = store.get_asset(asset_id)
                        path = store.asset_path(asset_id)
                        size_bytes = path.stat().st_size
                        if size_bytes > WORKSPACE_TRANSPORT_LIMIT:
                            reduced = thumbnails.preview(path, asset.mime_type)
                            result = {
                                "mime_type": reduced.mime_type,
                                "base64": base64.b64encode(reduced.content).decode("ascii"),
                                "reduced": True,
                                "original_mime_type": asset.mime_type,
                                "original_size_bytes": size_bytes,
                                "width": reduced.width,
                                "height": reduced.height,
                            }
                        else:
                            result = {
                                "mime_type": asset.mime_type,
                                "base64": base64.b64encode(path.read_bytes()).decode("ascii"),
                                "reduced": False,
                            }
                    elif method == "assets.bytes":
                        # 原寸を端末へ持ち出すための経路。表示用の縮小版とは別で
                        # ある（縮小版を保存すると、小さくなったことに気づかない
                        # まま原寸を失う）。1 度に運ぶ量を区切るのは、base64 が
                        # 4/3 に膨らんだうえで 1 つの socket message に載るため。
                        asset_id = str(params.get("asset_id", ""))
                        asset = store.get_asset(asset_id)
                        path = store.asset_path(asset_id)
                        total = path.stat().st_size
                        offset = params.get("offset", 0)
                        length = params.get("length", ASSET_CHUNK_BYTES)
                        if (
                            isinstance(offset, bool) or not isinstance(offset, int)
                            or isinstance(length, bool) or not isinstance(length, int)
                            or offset < 0 or offset > total or not 1 <= length <= ASSET_CHUNK_BYTES
                        ):
                            raise ValueError("asset byte range is out of bounds")
                        with path.open("rb") as stream:
                            stream.seek(offset)
                            chunk = stream.read(length)
                        result = {
                            "mime_type": asset.mime_type,
                            "filename": asset.suggested_filename,
                            "total_bytes": total,
                            "offset": offset,
                            "base64": base64.b64encode(chunk).decode("ascii"),
                        }
                    elif method == "reference_collections.list":
                        result = {"items": [
                            item.model_dump(mode="json") for item in store.list_reference_collections()
                        ]}
                    elif method == "reference_collections.create":
                        result = store.create_reference_collection(
                            ReferenceCollectionInput.model_validate(params)
                        ).model_dump(mode="json")
                    elif method == "reference_collections.delete":
                        store.delete_reference_collection(str(params.get("collection_id", "")))
                        result = {"deleted": True}
                    elif method == "profiles.list":
                        result = {"items": [item.model_dump(mode="json") for item in store.list_profiles()]}
                    elif method == "profiles.create":
                        result = store.create_profile(ProfileInput.model_validate(params)).model_dump(mode="json")
                    elif method == "profiles.delete":
                        store.delete_profile(str(params.get("profile_id", "")))
                        result = {"deleted": True}
                    elif method == "models.list":
                        # 開くたびに帳尻を合わせる。再起動で消えた評価をここで拾う。
                        start_pending_lora_base_evaluations(identity)
                        result = model_catalog()
                    elif method == "models.catalog":
                        if model_operations is None:
                            raise ModelOperationError("model_not_found", "model catalog is unavailable")
                        result = model_operations.catalog()
                        result["evaluation"] = {
                            "available_model_ids": model_evaluations.available_model_ids()
                            if model_evaluations is not None else []
                        }
                    elif method == "models.install":
                        if model_operations is None:
                            raise ModelOperationError("model_not_found", "model catalog is unavailable")
                        acceptance = params.get("license_acceptance")
                        if acceptance is not None and not isinstance(acceptance, str):
                            raise ValueError("license_acceptance must be a string")
                        installed = model_operations.install(
                            str(params.get("model_id", "")),
                            license_acceptance=acceptance,
                        )
                        # 落とした先が、導入済み LoRA の待っていた土台かもしれない。
                        # 誰かが画面を開くまで待たない。
                        follow_install(installed.id, identity)
                        result = installed.model_dump(mode="json")
                    elif method == "models.remove":
                        if model_operations is None:
                            raise ModelOperationError("model_not_found", "model catalog is unavailable")
                        result = model_operations.remove(str(params.get("model_id", ""))).model_dump(mode="json")
                    elif method == "models.evaluate":
                        if model_evaluations is None:
                            raise ModelOperationError(
                                "model_runtime_unavailable",
                                "model evaluator is unavailable",
                            )
                        if set(params) != {"model_id"}:
                            raise ValueError("model evaluation accepts only model_id")
                        result = model_evaluations.evaluate(
                            str(params.get("model_id", "")),
                            identity,
                        ).model_dump(mode="json")
                    elif method == "models.custom.search":
                        # 探せることと入れてよいことは別。ここは候補を返すだけで、
                        # 取り込みは従来どおり resolve と明示承諾を通す。
                        result = {
                            "items": annotate_candidates(await custom_models.search_source(
                                str(params.get("source", DEFAULT_MODEL_SOURCE)),
                                str(params.get("query", "")),
                                sort=str(params.get("sort", "downloads")),
                                model_type=str(params.get("model_type", "checkpoint")),
                            )),
                            "sort": str(params.get("sort", "downloads")),
                            "source": str(params.get("source", DEFAULT_MODEL_SOURCE)),
                            "model_type": str(params.get("model_type", "checkpoint")),
                            # 画面がここから「手元に載せられるか」を出せるようにする。
                            "installed_families": sorted(installed_families()),
                        }
                    elif method == "models.custom.lora_base":
                        # LoRA だけ落としても絵は作れない。押す前に、載せる先が
                        # 手元にあるか、無ければ何をいくら落とすことになるかを返す。
                        result = await custom_models.lora_base_requirement(
                            str(params.get("base_model", "")),
                            installed_families(),
                        )
                    elif method == "models.custom.resolve":
                        # 取得前に必ず解決して見せる。承諾は本文の提示が先。
                        resolution = await custom_models.resolve_source(
                            str(params.get("source", "")),
                            str(params.get("repo_id", "")),
                            str(params.get("revision", "main")),
                        )
                        result = resolution.document()
                        if resolution.runtime_adapter == "lora.diffusers":
                            report = await custom_models.lora_base_requirement(
                                str(resolution.runtime_options.get("base_model", "")),
                                installed_families(),
                            )
                            result["base_satisfied"] = report["satisfied"]
                            candidate = report.get("candidate")
                            if not report["satisfied"] and isinstance(candidate, dict):
                                dependency = await custom_models.resolve_source(
                                    "civitai",
                                    str(candidate.get("repo_id", "")),
                                    str(candidate.get("revision", "main")),
                                )
                                result["dependency"] = {
                                    **dependency.document(),
                                    "display_name": str(
                                        candidate.get("display_name") or dependency.repo_id
                                    ),
                                }
                    elif method == "models.custom.add":
                        resolution = await custom_models.resolve_source(
                            str(params.get("source", "")),
                            str(params.get("repo_id", "")),
                            str(params.get("revision", "main")),
                        )
                        domains = params.get("domains", ["general"])
                        if not isinstance(domains, list) or not all(
                            isinstance(value, str) for value in domains
                        ):
                            raise ValueError("custom model domains must be a list of strings")
                        bundle = [(
                            resolution,
                            str(params.get("display_name", "")),
                            str(params.get("license_acceptance", "")),
                        )]
                        dependency = None
                        if resolution.runtime_adapter == "lora.diffusers":
                            report = await custom_models.lora_base_requirement(
                                str(resolution.runtime_options.get("base_model", "")),
                                installed_families(),
                            )
                            if not report["satisfied"]:
                                dependency_params = params.get("dependency")
                                if not isinstance(dependency_params, dict):
                                    raise CustomModelError(
                                        "lora_base_required",
                                        "この LoRA に必要な土台を解決し直してください",
                                    )
                                dependency = await custom_models.resolve_source(
                                    "civitai",
                                    str(dependency_params.get("repo_id", "")),
                                    str(dependency_params.get("revision", "main")),
                                )
                                from .models.generation_defaults import normalize_base_model

                                if normalize_base_model(str(
                                    dependency.runtime_options.get("base_model", "")
                                )) != normalize_base_model(str(
                                    resolution.runtime_options.get("base_model", "")
                                )):
                                    raise CustomModelError(
                                        "lora_base_incompatible",
                                        "解決した土台はこの LoRA の系統と一致しません",
                                    )
                                bundle.append((
                                    dependency,
                                    str(dependency_params.get("display_name", dependency.repo_id)),
                                    str(dependency_params.get("license_acceptance", "")),
                                ))
                        entries = custom_models.add_bundle(
                            tuple(bundle), domains=tuple(domains) or ("general",)
                        )
                        # 追加分も shipped catalog と同じ parser で検証してから返す。
                        # ここで通らない entry を残さない。
                        try:
                            if model_operations is not None:
                                model_operations.catalog()
                        except ModelRegistryError:
                            for entry in entries:
                                custom_models.remove(entry["registry"]["model_id"])
                            raise
                        operations = []
                        install_ids: dict[str, str] = {}
                        if model_operations is not None:
                            # 小さい LoRA を先に確定し、その同じ要求で土台も取得する。
                            # installer 自体は直列なので同時に巨大ファイルを競合させない。
                            for entry in entries:
                                model_id = entry["registry"]["model_id"]
                                try:
                                    operation = model_operations.install(model_id)
                                except ModelOperationError as exc:
                                    if exc.code != "model_already_installed":
                                        raise
                                else:
                                    operations.append(operation.model_dump(mode="json"))
                                    install_ids[model_id] = operation.id
                        if dependency is not None:
                            dependency_id = entries[1]["registry"]["model_id"]
                            install_id = install_ids.get(dependency_id)
                            if install_id is not None:
                                follow_install(install_id, identity)
                            elif model_evaluations is not None:
                                try:
                                    evaluation = model_evaluations.evaluate(
                                        dependency_id, identity
                                    )
                                except ModelOperationError:
                                    pass
                                else:
                                    operations.append(
                                        evaluation.model_dump(mode="json")
                                    )
                        result = {
                            "model_id": entries[0]["registry"]["model_id"],
                            **resolution.document(),
                            "operations": operations,
                            **({"dependency_model_id": entries[1]["registry"]["model_id"]}
                               if len(entries) > 1 else {}),
                        }
                        session_events.publish("model_catalog")
                    elif method == "models.custom.remove":
                        custom_models.remove(str(params.get("model_id", "")))
                        result = {"removed": True}
                        session_events.publish("model_catalog")
                    elif method == "models.operations.list":
                        result = {
                            "items": [item.model_dump(mode="json") for item in store.list_model_operations()]
                        }
                    elif method == "models.operations.clear":
                        result = {"removed": store.clear_finished_model_operations()}
                    elif method == "models.operations.cancel":
                        if model_operations is None:
                            raise ModelOperationError("model_not_found", "model catalog is unavailable")
                        result = model_operations.cancel(
                            str(params.get("operation_id", ""))
                        ).model_dump(mode="json")
                    elif method == "models.operations.watch":
                        operation_ids = params.get("operation_ids", [])
                        if not isinstance(operation_ids, list) or not all(
                            isinstance(value, str) for value in operation_ids
                        ):
                            raise ValueError("operation_ids must be a list of strings")
                        watched = operation_ids or [
                            item.id for item in store.list_model_operations(20)
                            if item.state not in TERMINAL_MODEL_OPERATION_STATES
                        ]
                        result = {"watching": model_subscription.watch(watched)}
                    elif method == "models.operations.unwatch":
                        operation_ids = params.get("operation_ids", [])
                        if not isinstance(operation_ids, list) or not all(
                            isinstance(value, str) for value in operation_ids
                        ):
                            raise ValueError("operation_ids must be a list of strings")
                        result = {"watching": model_subscription.unwatch(operation_ids)}
                    elif method == "creative.templates":
                        result = creative_compiler.catalog.public_document()
                    elif method == "references.analyze":
                        result = await analyze_reference(params, identity)
                    elif method == "creative.direct":
                        creative_spec = CreativeSpec.model_validate(params.get("creative_spec", {}))
                        reference_context = accepted_reference_context(params)
                        directed = await creative_director.direct(
                            identity,
                            str(params.get("intent", "")),
                            creative_spec.model_dump(mode="json"),
                            mode=params_director_mode(params),
                            reference_context=reference_context,
                        )
                        # Re-validate the projection before it crosses back to the UI.
                        CreativeSpec.model_validate(directed.creative_spec)
                        result = directed.model_dump(mode="json")
                    elif method == "creative.prompt_recipe":
                        if set(params) != {"recipe_id", "request"}:
                            raise ValueError("prompt recipe accepts only recipe_id and request")
                        if params.get("recipe_id") != "minimax-h3-prompt-writing":
                            raise ValueError("prompt recipe is not supported")
                        result = (
                            await prompt_recipe.project(
                                identity,
                                PromptRecipeRequest.model_validate(params.get("request")),
                            )
                        ).model_dump(mode="json")
                    elif method == "creative.validate":
                        request = JobRequest.model_validate(params.get("request"))
                        creative_spec = CreativeSpec.model_validate(params.get("creative_spec", {}))
                        director_plan = (
                            PromptPlan.model_validate(params["director_plan"])
                            if params.get("director_plan") is not None else None
                        )
                        reference_context = accepted_reference_context(params)
                        profile_snapshot = manager.resolve_profiles(request)
                        available_references = {
                            item.asset_id for item in request.inputs
                        } | set(profile_snapshot.get("reference_asset_ids", []))
                        capability_value = await capability_document(identity)
                        result = compile_creative(
                            request,
                            creative_spec,
                            capabilities=capability_value["capabilities"],
                            available_references=available_references,
                            director_plan=director_plan,
                            reference_context=reference_context,
                        ).model_dump(mode="json")
                    elif method == "creative.batches.create":
                        async def submit_batch_child(child: JobRequest) -> dict[str, Any]:
                            return await submit_hosted(child, identity, workload_class="interactive")

                        result = await create_creative_batch(params, submit_batch_child, identity)
                    elif method == "creative.batches.get":
                        result = batch_projection(store.get_creative_batch(str(params.get("batch_id", ""))))
                    elif method == "creative.batches.list":
                        result = {"items": [batch_projection(item) for item in store.list_creative_batches()]}
                    elif method == "creative.batches.cancel":
                        result = await cancel_creative_batch(str(params.get("batch_id", "")))
                    elif method == "creative.compositions.create":
                        async def submit_composition_child(child: JobRequest) -> dict[str, Any]:
                            return await submit_hosted(child, identity, workload_class="interactive")

                        result = await create_creative_composition(
                            params, submit_composition_child, identity
                        )
                    elif method == "creative.compositions.get":
                        result = composition_projection(
                            store.get_creative_composition(str(params.get("composition_id", "")))
                        )
                    elif method == "creative.compositions.list":
                        result = {
                            "items": [
                                composition_projection(item)
                                for item in store.list_creative_compositions()
                            ]
                        }
                    elif method == "creative.compositions.update_text":
                        result = recompose_creative_composition(
                            str(params.get("composition_id", "")), params
                        )
                    elif method == "creative.compositions.cancel":
                        result = await cancel_creative_composition(
                            str(params.get("composition_id", ""))
                        )
                    elif method == "creative.evaluate":
                        result = await evaluate_creative_candidates(params, identity)
                    elif method == "scenes.list":
                        if params:
                            raise ValueError("scene list accepts no parameters")
                        result = {"items": [
                            item.model_dump(mode="json")
                            for item in scenes.list(preferences.subject_of(identity))
                        ]}
                    elif method == "scenes.get":
                        if set(params) != {"scene_id"}:
                            raise ValueError("scene get accepts only scene_id")
                        document, revisions = scenes.get(
                            preferences.subject_of(identity), str(params.get("scene_id", ""))
                        )
                        result = {
                            "scene": document.model_dump(mode="json"),
                            "revisions": [item.model_dump(mode="json") for item in revisions],
                        }
                    elif method == "scenes.import.begin":
                        if set(params) - {"size", "sha256", "name", "tags", "collection"} or not {
                            "size", "sha256", "name"
                        } <= set(params):
                            raise ValueError("scene import declaration fields differ")
                        result = scene_workspace.begin_upload(
                            preferences.subject_of(identity),
                            size=params.get("size"),
                            sha256=params.get("sha256"),
                            name=params.get("name"),
                            tags=params.get("tags"),
                            collection=params.get("collection"),
                        )
                        scene_upload_ids.add(result["upload_id"])
                    elif method == "scenes.import.chunk":
                        if set(params) != {"upload_id", "offset", "sha256", "base64"}:
                            raise ValueError("scene import chunk fields differ")
                        encoded = params.get("base64")
                        if not isinstance(encoded, str) or len(encoded) > 700_000:
                            raise ValueError("scene import chunk encoding is invalid")
                        try:
                            content = base64.b64decode(encoded, validate=True)
                        except ValueError as exc:
                            raise ValueError("scene import chunk is not valid base64") from exc
                        result = scene_workspace.append_upload(
                            preferences.subject_of(identity),
                            str(params.get("upload_id", "")),
                            params.get("offset"),
                            content,
                            str(params.get("sha256", "")),
                        )
                    elif method == "scenes.import.commit":
                        if set(params) != {"upload_id"}:
                            raise ValueError("scene import commit accepts only upload_id")
                        upload_id = str(params.get("upload_id", ""))
                        try:
                            result = await scene_workspace.commit_upload(
                                preferences.subject_of(identity), upload_id
                            )
                        finally:
                            scene_upload_ids.discard(upload_id)
                    elif method == "scenes.import.cancel":
                        if set(params) != {"upload_id"}:
                            raise ValueError("scene import cancel accepts only upload_id")
                        upload_id = str(params.get("upload_id", ""))
                        result = {"canceled": scene_workspace.cancel_upload(
                            preferences.subject_of(identity), upload_id
                        )}
                        scene_upload_ids.discard(upload_id)
                    elif method == "scenes.working.acquire":
                        if set(params) != {"scene_id"}:
                            raise ValueError("working copy acquire accepts only scene_id")
                        result = scene_workspace.acquire_working_copy(
                            preferences.subject_of(identity), str(params.get("scene_id", ""))
                        ).model_dump(mode="json")
                    elif method == "scenes.working.renew":
                        if set(params) != {"working_id"}:
                            raise ValueError("working copy renew accepts only working_id")
                        result = scene_workspace.renew_working_copy(
                            preferences.subject_of(identity), str(params.get("working_id", ""))
                        ).model_dump(mode="json")
                    elif method == "scenes.working.release":
                        if set(params) != {"working_id"}:
                            raise ValueError("working copy release accepts only working_id")
                        result = scene_workspace.release_working_copy(
                            preferences.subject_of(identity), str(params.get("working_id", ""))
                        ).model_dump(mode="json")
                    elif method == "scenes.working.commit":
                        if set(params) != {"working_id"}:
                            raise ValueError("working copy commit accepts only working_id")
                        result = await scene_workspace.commit_working_copy(
                            preferences.subject_of(identity), str(params.get("working_id", ""))
                        )
                    elif method == "scenes.backup.open":
                        if set(params) != {"scene_id"}:
                            raise ValueError("scene backup open accepts only scene_id")
                        result = await asyncio.to_thread(
                            scene_backups.open_download,
                            preferences.subject_of(identity),
                            str(params.get("scene_id", "")),
                        )
                    elif method == "scenes.backup.read":
                        if not {"handle", "offset"} <= set(params) or set(params) - {
                            "handle",
                            "offset",
                            "length",
                        }:
                            raise ValueError(
                                "scene backup read accepts handle, offset, and length"
                            )
                        result = await asyncio.to_thread(
                            scene_backups.read_download,
                            preferences.subject_of(identity),
                            str(params.get("handle", "")),
                            params.get("offset"),
                            params.get("length", 512 * 1024),
                        )
                    elif method == "scenes.backup.close":
                        if set(params) != {"handle"}:
                            raise ValueError("scene backup close accepts only handle")
                        result = {
                            "closed": await asyncio.to_thread(
                                scene_backups.close_download,
                                preferences.subject_of(identity),
                                str(params.get("handle", "")),
                            )
                        }
                    elif method == "scenes.restore.begin":
                        if set(params) != {"size", "sha256"}:
                            raise ValueError("scene restore begin accepts size and sha256")
                        result = scene_backups.begin_restore(
                            preferences.subject_of(identity),
                            size=params.get("size"),
                            sha256=params.get("sha256"),
                        )
                    elif method == "scenes.restore.chunk":
                        if set(params) != {"upload_id", "offset", "sha256", "base64"}:
                            raise ValueError("scene restore chunk fields differ")
                        encoded = params.get("base64")
                        if not isinstance(encoded, str) or len(encoded) > 700_000:
                            raise ValueError("scene restore chunk encoding is invalid")
                        try:
                            content = base64.b64decode(encoded, validate=True)
                        except ValueError as exc:
                            raise ValueError("scene restore chunk is not valid base64") from exc
                        result = scene_backups.append_restore(
                            preferences.subject_of(identity),
                            str(params.get("upload_id", "")),
                            params.get("offset"),
                            content,
                            params.get("sha256"),
                        )
                    elif method == "scenes.restore.commit":
                        if set(params) != {"upload_id"}:
                            raise ValueError("scene restore commit accepts only upload_id")
                        result = await asyncio.to_thread(
                            scene_backups.commit_restore,
                            preferences.subject_of(identity),
                            str(params.get("upload_id", "")),
                        )
                    elif method == "scenes.restore.cancel":
                        if set(params) != {"upload_id"}:
                            raise ValueError("scene restore cancel accepts only upload_id")
                        result = {
                            "canceled": scene_backups.cancel_restore(
                                preferences.subject_of(identity),
                                str(params.get("upload_id", "")),
                            )
                        }
                    elif method == "workspace.session":
                        # 状態の正はサーバにある。boot も更新もこの 1 メソッドで足りる。
                        result = await session_snapshot(
                            identity, requested_session_parts(params)
                        )
                        if "jobs" in result and isinstance(result["jobs"], dict):
                            watched = [
                                item["id"] for item in result["jobs"].get("items", [])
                                if item.get("status") not in TERMINAL_JOB_STATES
                            ]
                            result["watching"] = {"jobs": subscription.watch(watched)}
                        if "model_operations" in result and isinstance(result["model_operations"], dict):
                            active = [
                                item["id"] for item in result["model_operations"].get("items", [])
                                if item.get("state") not in {
                                    state.value for state in TERMINAL_MODEL_OPERATION_STATES
                                }
                            ]
                            result.setdefault("watching", {})["model_operations"] = (
                                model_subscription.watch(active)
                            )
                    elif method == "capabilities.get":
                        envelope = size_envelope()
                        result = {
                            **await capability_document(identity),
                            "envelope": envelope,
                            "presets": size_presets(envelope),
                            "device": {"vram_bytes": device_vram_bytes()},
                        }
                    elif method == "blender.runtime.status":
                        result = blender_runtime_part()
                    elif method == "blender.runtime.install":
                        if params:
                            raise ValueError("Blender install accepts no client-selected source")
                        result = blender_runtime_operations.install().model_dump(mode="json")
                    elif method == "blender.web.install":
                        if params:
                            raise ValueError("Blender web pack install accepts no client-selected source")
                        result = blender_runtime_operations.install_web().model_dump(mode="json")
                    elif method == "blender.runtime.update":
                        if params:
                            raise ValueError("Blender update accepts no client-selected source")
                        result = blender_runtime_operations.update().model_dump(mode="json")
                    elif method == "blender.runtime.repair":
                        if set(params) != {"runtime_id"}:
                            raise ValueError("Blender repair accepts only runtime_id")
                        result = blender_runtime_operations.repair(
                            str(params.get("runtime_id", ""))
                        ).model_dump(mode="json")
                    elif method == "blender.runtime.switch":
                        if set(params) != {"runtime_id"}:
                            raise ValueError("Blender switch accepts only runtime_id")
                        result = blender_runtime_operations.switch(
                            str(params.get("runtime_id", ""))
                        ).model_dump(mode="json")
                    elif method == "blender.runtime.remove.preview":
                        if set(params) != {"runtime_id"}:
                            raise ValueError("Blender removal preview accepts only runtime_id")
                        result = blender_runtime_operations.removal_preview(
                            str(params.get("runtime_id", ""))
                        )
                    elif method == "blender.runtime.remove":
                        if set(params) != {"runtime_id", "confirmation_fingerprint"}:
                            raise ValueError(
                                "Blender remove accepts runtime_id and confirmation_fingerprint"
                            )
                        result = blender_runtime_operations.remove(
                            str(params.get("runtime_id", "")),
                            str(params.get("confirmation_fingerprint", "")),
                        ).model_dump(mode="json")
                    elif method == "blender.runtime.operations.cancel":
                        if set(params) != {"operation_id"}:
                            raise ValueError("Blender cancel accepts only operation_id")
                        result = blender_runtime_operations.cancel(
                            str(params.get("operation_id", ""))
                        ).model_dump(mode="json")
                    elif method == "blender.sessions.list":
                        if params:
                            raise ValueError("Blender session list accepts no parameters")
                        result = blender_sessions.list(preferences.subject_of(identity))
                    elif method == "blender.sessions.start":
                        if set(params) != {"scene_id"}:
                            raise ValueError("Blender session start accepts only scene_id")
                        result = blender_sessions.create(
                            preferences.subject_of(identity), str(params.get("scene_id", ""))
                        )
                    elif method == "blender.sessions.save":
                        if set(params) != {"session_id"}:
                            raise ValueError("Blender session save accepts only session_id")
                        result = blender_sessions.save_and_stop(
                            preferences.subject_of(identity), str(params.get("session_id", ""))
                        )
                    elif method == "blender.sessions.stop":
                        if set(params) != {"session_id"}:
                            raise ValueError("Blender session stop accepts only session_id")
                        result = blender_sessions.discard_and_stop(
                            preferences.subject_of(identity), str(params.get("session_id", ""))
                        )
                    elif method == "library.list":
                        kind = params.get("kind", "all")
                        if kind not in library.KINDS:
                            raise ValueError("library kind is not supported")
                        media_kind = params.get("media_kind", "all")
                        if media_kind not in library.MEDIA_KINDS:
                            raise ValueError("library media kind is not supported")
                        before = params.get("before")
                        if before is not None and not isinstance(before, str):
                            raise ValueError("library cursor must be a string")
                        limit = library.clamp_limit(params.get("limit"))
                        result = library.page(
                            store.list_asset_records(limit, before),
                            kind=str(kind),
                            include_masks=params.get("include_masks") is True,
                            limit=limit,
                            media_kind=str(media_kind),
                            # 既定で同梱する。呼び出し側が明示的に切れる。
                            thumbnail=None if params.get("thumbnails") is False else grid_thumbnail,
                        )
                    elif method == "assets.delete":
                        # 複数選択できるので、1 件ずつの結果を返す。1 件の失敗で
                        # 全部を消さなかったのか、どれが残ったのかを言えるようにする。
                        asset_ids = params.get("asset_ids")
                        if not isinstance(asset_ids, list) or not asset_ids or len(asset_ids) > 100:
                            raise ValueError("asset_ids must be a list of 1..100 asset IDs")
                        outcomes = []
                        for value in asset_ids:
                            asset_id = str(value)
                            try:
                                store.delete_asset(asset_id)
                                outcomes.append({"asset_id": asset_id, "deleted": True})
                            except AssetInUse as exc:
                                outcomes.append({
                                    "asset_id": asset_id, "deleted": False,
                                    "code": exc.code, "message": str(exc)[:200],
                                })
                            except KeyError:
                                outcomes.append({
                                    "asset_id": asset_id, "deleted": False,
                                    "code": "asset_not_found", "message": "already gone",
                                })
                        result = {
                            "items": outcomes,
                            "deleted_count": sum(1 for item in outcomes if item["deleted"]),
                        }
                    elif method == "assets.export":
                        # 設計 §F4 保存A。実装済みの host files bridge を UI から
                        # 使えるようにする。ここまで導線が 1 つも無かった。
                        asset_id = str(params.get("asset_id", ""))
                        asset = store.get_asset(asset_id)
                        filename = placement_filename(
                            requested=params.get("filename"),
                            suggested=asset.suggested_filename,
                            mime_type=asset.mime_type,
                        )
                        attached = await host.create_or_attach_job(
                            identity, title="Media Forge export"
                        )
                        host_job = attached.get("job")
                        if not isinstance(host_job, dict) or not isinstance(host_job.get("id"), str):
                            raise HostApiError("invalid_host_response", "ControlDeck did not attach a job", 502)
                        committed = await commit_file(
                            host,
                            identity,
                            host_job_id=host_job["id"],
                            grant_id=require_grant_id(str(params.get("export_grant_id", ""))),
                            source=store.asset_path(asset_id),
                            filename=filename,
                            mime_type=asset.mime_type,
                            sha256=asset.sha256,
                        )
                        if attached.get("created") is True:
                            await host.update_job(identity, host_job["id"], {
                                "phase": "package",
                                "progress": {"completed": 1, "total": 1},
                                "status": "succeeded",
                                "result": {"asset_id": committed.get("asset_id")},
                            })
                        # 受領書と同じ形で返す。書き出したものを ls で確かめ直させない。
                        result = PlacementReceipt(
                            committed=True,
                            source_asset_id=asset.id,
                            host_asset_id=committed.get("asset_id"),
                            filename=filename,
                            media_type=asset.mime_type,
                            sha256=asset.sha256,
                            size_bytes=asset.size_bytes,
                            width=asset.width,
                            height=asset.height,
                        ).model_dump(mode="json")
                    elif method == "assets.thumbnail":
                        asset_id = str(params.get("asset_id", ""))
                        asset = store.get_asset(asset_id)
                        if asset.mime_type == "model/gltf-binary":
                            thumbnail = thumbnails.model_cached(
                                store.thumbnail_dir,
                                asset_id,
                                thumbnails.clamp_max_side(params.get("max_side")),
                            )
                        elif not thumbnails.is_thumbnailable(asset.mime_type):
                            raise ThumbnailError()
                        else:
                            thumbnail = thumbnails.cached(
                                store.asset_path(asset_id),
                                store.thumbnail_dir,
                                asset_id,
                                thumbnails.clamp_max_side(params.get("max_side")),
                                asset.mime_type,
                            )
                        result = {
                            "mime_type": thumbnail.mime_type,
                            "width": thumbnail.width,
                            "height": thumbnail.height,
                            "base64": base64.b64encode(thumbnail.content).decode("ascii"),
                        }
                    elif method == "preferences.get":
                        result = {"values": preferences.merged(
                            store.get_preferences(preferences.subject_of(identity))
                        )}
                    elif method == "preferences.set":
                        payload = params.get("values")
                        if len(json.dumps(payload, ensure_ascii=False).encode()) > preferences.MAX_PAYLOAD_BYTES:
                            raise PreferenceError("preferences_too_large", "preferences exceed the stored bound")
                        subject = preferences.subject_of(identity)
                        stored = preferences.merged(store.get_preferences(subject))
                        stored.update(preferences.validate(payload))
                        result = {"values": store.set_preferences(subject, stored)}
                    elif method == "jobs.watch":
                        job_ids = params.get("job_ids", [])
                        if not isinstance(job_ids, list) or not all(isinstance(value, str) for value in job_ids):
                            raise ValueError("job_ids must be a list of strings")
                        watched = job_ids or [
                            item.id for item in store.list_jobs(20)
                            if item.status.value not in TERMINAL_JOB_STATES
                        ]
                        result = {"watching": subscription.watch(watched)}
                    elif method == "jobs.unwatch":
                        job_ids = params.get("job_ids", [])
                        if not isinstance(job_ids, list) or not all(isinstance(value, str) for value in job_ids):
                            raise ValueError("job_ids must be a list of strings")
                        result = {"watching": subscription.unwatch(job_ids)}
                    else:
                        raise ValueError("workspace method is not supported")
                    await websocket.send_json({"id": request_id, "ok": True, "result": result})
                except (
                    ThumbnailError,
                    ModelViewerError,
                    PreferenceError,
                    ModelOperationError,
                    BlenderRuntimeOperationError,
                    BlenderSessionError,
                    CustomModelError,
                    CreativeValidationError,
                    ReferenceIntelligenceError,
                    PromptRecipeError,
                    SceneError,
                ) as exc:
                    error = {"code": exc.code, "message": str(exc)[:300]}
                    if isinstance(exc, CreativeValidationError) and exc.field is not None:
                        error["field"] = exc.field
                    await websocket.send_json({
                        "id": request_id,
                        "ok": False,
                        "error": error,
                    })
                except CreativeEvaluationError as exc:
                    await websocket.send_json({
                        "id": request_id,
                        "ok": False,
                        "error": {"code": exc.code, "message": str(exc)[:300]},
                    })
                except (KeyError, ValueError, ValidationError) as exc:
                    await websocket.send_json({
                        "id": request_id,
                        "ok": False,
                        "error": {"code": "workspace_request_rejected", "message": str(exc)[:300]},
                    })
                except HTTPException as exc:
                    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "workspace_request_rejected"}
                    await websocket.send_json({"id": request_id, "ok": False, "error": detail})
        except WebSocketDisconnect:
            return
        finally:
            subscription.close()
            model_subscription.close()
            session_subscription.close()
            model_sender.cancel()
            session_sender.cancel()
            await asyncio.gather(model_sender, session_sender, return_exceptions=True)
            sender.cancel()
            for upload in uploads.values():
                root = upload.get("root")
                if isinstance(root, Path) and root.exists():
                    shutil.rmtree(root)
            for upload_id in scene_upload_ids:
                try:
                    scene_workspace.cancel_upload(preferences.subject_of(identity), upload_id)
                except SceneError:
                    continue
            await asyncio.to_thread(model_viewer.cleanup)
            await asyncio.to_thread(scene_backups.cleanup)

    @app.post("/workspace-api/jobs/clear", include_in_schema=False)
    async def standalone_clear_jobs() -> dict[str, Any]:
        """Same-origin workspace bridge for standalone mode; not a public API."""
        return {"cleared": store.clear_finished_jobs()}

    @app.get("/workspace-api/scenes", include_in_schema=False)
    async def standalone_scenes() -> dict[str, Any]:
        return {
            "items": [
                item.model_dump(mode="json")
                for item in scenes.list(preferences.STANDALONE_SUBJECT)
            ]
        }

    @app.get("/workspace-api/scenes/{scene_id}", include_in_schema=False)
    async def standalone_scene(scene_id: str) -> dict[str, Any]:
        try:
            document, revisions = scenes.get(preferences.STANDALONE_SUBJECT, scene_id)
        except SceneError as exc:
            raise HTTPException(
                status_code=404, detail={"code": exc.code, "message": str(exc)}
            ) from exc
        return {
            "scene": document.model_dump(mode="json"),
            "revisions": [item.model_dump(mode="json") for item in revisions],
        }

    @app.post("/workspace-api/scenes/import/begin", include_in_schema=False)
    async def standalone_scene_import_begin(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            reject_host_paths(payload)
            if set(payload) - {"size", "sha256", "name", "tags", "collection"} or not {
                "size", "sha256", "name"
            } <= set(payload):
                raise SceneError("scene_upload_invalid", "scene import declaration fields differ")
            return scene_workspace.begin_upload(
                preferences.STANDALONE_SUBJECT,
                size=payload.get("size"),
                sha256=payload.get("sha256"),
                name=payload.get("name"),
                tags=payload.get("tags"),
                collection=payload.get("collection"),
            )
        except SceneError as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc

    @app.post("/workspace-api/scenes/import/chunk", include_in_schema=False)
    async def standalone_scene_import_chunk(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            reject_host_paths(payload)
            if set(payload) != {"upload_id", "offset", "sha256", "base64"}:
                raise SceneError("scene_upload_chunk_invalid", "scene import chunk fields differ")
            encoded = payload.get("base64")
            if not isinstance(encoded, str) or len(encoded) > 700_000:
                raise SceneError("scene_upload_chunk_invalid", "scene upload encoding is invalid")
            content = base64.b64decode(encoded, validate=True)
            return scene_workspace.append_upload(
                preferences.STANDALONE_SUBJECT,
                str(payload.get("upload_id", "")),
                payload.get("offset"),
                content,
                str(payload.get("sha256", "")),
            )
        except (SceneError, ValueError) as exc:
            code = getattr(exc, "code", "scene_upload_chunk_invalid")
            raise HTTPException(status_code=422, detail={"code": code, "message": str(exc)}) from exc

    @app.post("/workspace-api/scenes/import/commit", include_in_schema=False)
    async def standalone_scene_import_commit(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            reject_host_paths(payload)
            if set(payload) != {"upload_id"}:
                raise SceneError("scene_upload_invalid", "scene import commit fields differ")
            return await scene_workspace.commit_upload(
                preferences.STANDALONE_SUBJECT, str(payload.get("upload_id", ""))
            )
        except SceneError as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc

    @app.post("/workspace-api/scenes/import/cancel", include_in_schema=False)
    async def standalone_scene_import_cancel(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            reject_host_paths(payload)
            if set(payload) != {"upload_id"}:
                raise SceneError("scene_upload_invalid", "scene import cancel fields differ")
            return {"canceled": scene_workspace.cancel_upload(
                preferences.STANDALONE_SUBJECT, str(payload.get("upload_id", ""))
            )}
        except SceneError as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc

    @app.post("/workspace-api/scenes/{scene_id}/working", include_in_schema=False)
    async def standalone_scene_working_acquire(scene_id: str) -> dict[str, Any]:
        try:
            return scene_workspace.acquire_working_copy(
                preferences.STANDALONE_SUBJECT, scene_id
            ).model_dump(mode="json")
        except SceneError as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc

    @app.post("/workspace-api/scenes/{scene_id}/backup/open", include_in_schema=False)
    async def standalone_scene_backup_open(scene_id: str) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(
                standalone_scene_backups.open_download,
                preferences.STANDALONE_SUBJECT,
                scene_id,
            )
        except SceneError as exc:
            raise HTTPException(
                status_code=422, detail={"code": exc.code, "message": str(exc)}
            ) from exc

    @app.post("/workspace-api/scenes/backups/{handle}/read", include_in_schema=False)
    async def standalone_scene_backup_read(
        handle: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            reject_host_paths(payload)
            if set(payload) - {"offset", "length"} or "offset" not in payload:
                raise SceneError("scene_backup_range_invalid", "scene backup read fields differ")
            return await asyncio.to_thread(
                standalone_scene_backups.read_download,
                preferences.STANDALONE_SUBJECT,
                handle,
                payload.get("offset"),
                payload.get("length", 512 * 1024),
            )
        except SceneError as exc:
            raise HTTPException(
                status_code=422, detail={"code": exc.code, "message": str(exc)}
            ) from exc

    @app.post("/workspace-api/scenes/backups/{handle}/close", include_in_schema=False)
    async def standalone_scene_backup_close(handle: str) -> dict[str, bool]:
        return {
            "closed": await asyncio.to_thread(
                standalone_scene_backups.close_download,
                preferences.STANDALONE_SUBJECT,
                handle,
            )
        }

    @app.post("/workspace-api/scenes/restore/begin", include_in_schema=False)
    async def standalone_scene_restore_begin(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            reject_host_paths(payload)
            if set(payload) != {"size", "sha256"}:
                raise SceneError(
                    "scene_backup_upload_invalid", "scene restore declaration fields differ"
                )
            return standalone_scene_backups.begin_restore(
                preferences.STANDALONE_SUBJECT,
                size=payload.get("size"),
                sha256=payload.get("sha256"),
            )
        except SceneError as exc:
            raise HTTPException(
                status_code=422, detail={"code": exc.code, "message": str(exc)}
            ) from exc

    @app.post("/workspace-api/scenes/restore/chunk", include_in_schema=False)
    async def standalone_scene_restore_chunk(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            reject_host_paths(payload)
            if set(payload) != {"upload_id", "offset", "sha256", "base64"}:
                raise SceneError(
                    "scene_backup_chunk_invalid", "scene restore chunk fields differ"
                )
            encoded = payload.get("base64")
            if not isinstance(encoded, str) or len(encoded) > 700_000:
                raise SceneError(
                    "scene_backup_chunk_invalid", "scene restore chunk encoding is invalid"
                )
            content = base64.b64decode(encoded, validate=True)
            return standalone_scene_backups.append_restore(
                preferences.STANDALONE_SUBJECT,
                str(payload.get("upload_id", "")),
                payload.get("offset"),
                content,
                payload.get("sha256"),
            )
        except (SceneError, ValueError) as exc:
            code = getattr(exc, "code", "scene_backup_chunk_invalid")
            raise HTTPException(
                status_code=422, detail={"code": code, "message": str(exc)}
            ) from exc

    @app.post("/workspace-api/scenes/restore/commit", include_in_schema=False)
    async def standalone_scene_restore_commit(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            reject_host_paths(payload)
            if set(payload) != {"upload_id"}:
                raise SceneError(
                    "scene_backup_upload_invalid", "scene restore commit fields differ"
                )
            return await asyncio.to_thread(
                standalone_scene_backups.commit_restore,
                preferences.STANDALONE_SUBJECT,
                str(payload.get("upload_id", "")),
            )
        except SceneError as exc:
            raise HTTPException(
                status_code=422, detail={"code": exc.code, "message": str(exc)}
            ) from exc

    @app.post("/workspace-api/scenes/restore/cancel", include_in_schema=False)
    async def standalone_scene_restore_cancel(payload: dict[str, Any]) -> dict[str, bool]:
        try:
            reject_host_paths(payload)
            if set(payload) != {"upload_id"}:
                raise SceneError(
                    "scene_backup_upload_invalid", "scene restore cancel fields differ"
                )
            return {
                "canceled": standalone_scene_backups.cancel_restore(
                    preferences.STANDALONE_SUBJECT,
                    str(payload.get("upload_id", "")),
                )
            }
        except SceneError as exc:
            raise HTTPException(
                status_code=422, detail={"code": exc.code, "message": str(exc)}
            ) from exc

    @app.post("/workspace-api/scenes/working/{working_id}", include_in_schema=False)
    async def standalone_scene_working_action(
        working_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            if payload == {"action": "renew"}:
                return scene_workspace.renew_working_copy(
                    preferences.STANDALONE_SUBJECT, working_id
                ).model_dump(mode="json")
            if payload == {"action": "release"}:
                return scene_workspace.release_working_copy(
                    preferences.STANDALONE_SUBJECT, working_id
                ).model_dump(mode="json")
            if payload == {"action": "commit"}:
                return await scene_workspace.commit_working_copy(
                    preferences.STANDALONE_SUBJECT, working_id
                )
            raise SceneError("scene_working_action_invalid", "working copy action is invalid")
        except SceneError as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc

    @app.post("/workspace-api/assets/delete", include_in_schema=False)
    async def standalone_delete_assets(payload: dict[str, Any]) -> dict[str, Any]:
        """Same-origin workspace bridge for standalone mode; not a public API."""
        asset_ids = payload.get("asset_ids")
        if not isinstance(asset_ids, list) or not asset_ids or len(asset_ids) > 100:
            raise HTTPException(status_code=422, detail={"code": "invalid_asset_ids"})
        outcomes = []
        for value in asset_ids:
            asset_id = str(value)
            try:
                store.delete_asset(asset_id)
                outcomes.append({"asset_id": asset_id, "deleted": True})
            except AssetInUse as exc:
                outcomes.append({
                    "asset_id": asset_id, "deleted": False,
                    "code": exc.code, "message": str(exc)[:200],
                })
            except KeyError:
                outcomes.append({
                    "asset_id": asset_id, "deleted": False,
                    "code": "asset_not_found", "message": "already gone",
                })
        return {"items": outcomes, "deleted_count": sum(1 for i in outcomes if i["deleted"])}

    @app.get("/workspace-api/models/catalog", include_in_schema=False)
    async def standalone_model_catalog() -> dict[str, Any]:
        """Same-origin workspace bridge for standalone mode; not a public API.

        The standalone shim used to report management as unavailable, so the
        list could never offer download or delete. Managing local model files
        needs no Host, so report what is actually configured.
        """
        if model_operations is None:
            return {"items": [], "management_available": False}
        value = model_operations.catalog()
        value["evaluation"] = {
            "available_model_ids": model_evaluations.available_model_ids()
            if model_evaluations is not None else []
        }
        return value

    @app.get("/workspace-api/models/operations", include_in_schema=False)
    async def standalone_model_operations() -> dict[str, Any]:
        return {"items": [item.model_dump(mode="json") for item in store.list_model_operations()]}

    @app.get("/workspace-api/blender/runtime", include_in_schema=False)
    async def standalone_blender_runtime_status() -> dict[str, Any]:
        return blender_runtime_part()

    @app.post("/workspace-api/blender/runtime/operations", include_in_schema=False)
    async def standalone_blender_runtime_operation(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            if payload == {"action": "install"}:
                return blender_runtime_operations.install().model_dump(mode="json")
            if payload == {"action": "web_install"}:
                return blender_runtime_operations.install_web().model_dump(mode="json")
            if payload == {"action": "update"}:
                return blender_runtime_operations.update().model_dump(mode="json")
            if set(payload) == {"action", "runtime_id"} and payload["action"] == "repair":
                return blender_runtime_operations.repair(
                    str(payload["runtime_id"])
                ).model_dump(mode="json")
            if set(payload) == {"action", "runtime_id"} and payload["action"] == "switch":
                return blender_runtime_operations.switch(
                    str(payload["runtime_id"])
                ).model_dump(mode="json")
            if set(payload) == {"action", "runtime_id"} and payload["action"] == "remove_preview":
                return blender_runtime_operations.removal_preview(str(payload["runtime_id"]))
            if (
                set(payload) == {"action", "runtime_id", "confirmation_fingerprint"}
                and payload["action"] == "remove"
            ):
                return blender_runtime_operations.remove(
                    str(payload["runtime_id"]), str(payload["confirmation_fingerprint"])
                ).model_dump(mode="json")
            if set(payload) == {"action", "operation_id"} and payload["action"] == "cancel":
                return blender_runtime_operations.cancel(
                    str(payload["operation_id"])
                ).model_dump(mode="json")
        except BlenderRuntimeOperationError as exc:
            raise HTTPException(
                status_code=422, detail={"code": exc.code, "message": str(exc)[:300]}
            ) from exc
        raise HTTPException(status_code=422, detail={"code": "invalid_blender_runtime_action"})

    @app.get("/workspace-api/blender/sessions", include_in_schema=False)
    async def standalone_blender_sessions() -> dict[str, Any]:
        return blender_sessions.list(preferences.STANDALONE_SUBJECT)

    @app.post("/workspace-api/blender/sessions", include_in_schema=False)
    async def standalone_blender_session_action(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            reject_host_paths(payload)
            if set(payload) == {"action", "scene_id"} and payload["action"] == "start":
                return blender_sessions.create(
                    preferences.STANDALONE_SUBJECT, str(payload["scene_id"])
                )
            if set(payload) == {"action", "session_id"} and payload["action"] == "save":
                return blender_sessions.save_and_stop(
                    preferences.STANDALONE_SUBJECT, str(payload["session_id"])
                )
            if set(payload) == {"action", "session_id"} and payload["action"] == "stop":
                return blender_sessions.discard_and_stop(
                    preferences.STANDALONE_SUBJECT, str(payload["session_id"])
                )
        except BlenderSessionError as exc:
            raise HTTPException(
                status_code=422, detail={"code": exc.code, "message": str(exc)[:300]}
            ) from exc
        raise HTTPException(status_code=422, detail={"code": "invalid_blender_session_action"})

    @app.post("/workspace-api/models/operations", include_in_schema=False)
    async def standalone_model_operation(payload: dict[str, Any]) -> dict[str, Any]:
        if model_operations is None:
            raise HTTPException(status_code=503, detail={"code": "model_not_found"})
        action = payload.get("action")
        model_id = str(payload.get("model_id", ""))
        try:
            if action == "install":
                acceptance = payload.get("license_acceptance")
                return model_operations.install(
                    model_id,
                    license_acceptance=acceptance if isinstance(acceptance, str) else None,
                ).model_dump(mode="json")
            if action == "remove":
                return model_operations.remove(model_id).model_dump(mode="json")
            if action == "cancel":
                return model_operations.cancel(str(payload.get("operation_id", ""))).model_dump(mode="json")
            if action == "clear":
                return {"removed": store.clear_finished_model_operations()}
        except ModelOperationError as exc:
            raise HTTPException(
                status_code=422, detail={"code": exc.code, "message": str(exc)[:300]}
            ) from exc
        raise HTTPException(status_code=422, detail={"code": "invalid_model_action"})

    @app.post("/workspace-api/models/search", include_in_schema=False)
    async def standalone_model_search(payload: dict[str, Any]) -> dict[str, Any]:
        """Same-origin workspace bridge for standalone mode; not a public API.

        Searching the distribution site needs no Host at all, so the standalone
        workspace should be able to do it. Without this the search box was dead
        outside the embedded view.
        """
        try:
            reject_host_paths(payload)
            rows = await custom_models.search_source(
                str(payload.get("source", DEFAULT_MODEL_SOURCE)),
                str(payload.get("query", "")),
                sort=str(payload.get("sort", "downloads")),
                model_type=str(payload.get("model_type", "checkpoint")),
            )
        except CustomModelError as exc:
            raise HTTPException(
                status_code=502, detail={"code": exc.code, "message": str(exc)[:300]}
            ) from exc
        return {
            "items": annotate_candidates(rows),
            "installed_families": sorted(installed_families()),
        }

    @app.post("/workspace-api/creative/batches", include_in_schema=False)
    async def standalone_creative_batch(payload: dict[str, Any]) -> dict[str, Any]:
        async def submit_batch_child(child: JobRequest) -> dict[str, Any]:
            return manager.submit(child).model_dump(mode="json")

        try:
            reject_host_paths(payload)
            return await create_creative_batch(payload, submit_batch_child)
        except CreativeValidationError as exc:
            detail: dict[str, Any] = {"code": exc.code, "message": str(exc)}
            if exc.field is not None:
                detail["field"] = exc.field
            raise HTTPException(status_code=422, detail=detail) from exc
        except ReferenceIntelligenceError as exc:
            raise HTTPException(
                status_code=422, detail={"code": exc.code, "message": str(exc)[:300]}
            ) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "asset_not_found"}) from exc
        except (ProfileResolutionError, ValueError) as exc:
            code = exc.code if isinstance(exc, ProfileResolutionError) else "workspace_request_rejected"
            raise HTTPException(status_code=422, detail={"code": code, "message": str(exc)[:300]}) from exc

    @app.get("/workspace-api/creative/batches", include_in_schema=False)
    async def standalone_creative_batches() -> dict[str, Any]:
        return {"items": [batch_projection(item) for item in store.list_creative_batches()]}

    @app.get("/workspace-api/creative/batches/{batch_id}", include_in_schema=False)
    async def standalone_creative_batch_get(batch_id: str) -> dict[str, Any]:
        try:
            return batch_projection(store.get_creative_batch(batch_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "creative_batch_not_found"}) from exc

    @app.delete("/workspace-api/creative/batches/{batch_id}", include_in_schema=False)
    async def standalone_creative_batch_cancel(batch_id: str) -> dict[str, Any]:
        try:
            return await cancel_creative_batch(batch_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "creative_batch_not_found"}) from exc

    @app.post("/workspace-api/creative/compositions", include_in_schema=False)
    async def standalone_creative_composition(payload: dict[str, Any]) -> dict[str, Any]:
        async def submit_composition_child(child: JobRequest) -> dict[str, Any]:
            return manager.submit(child).model_dump(mode="json")

        try:
            reject_host_paths(payload)
            return await create_creative_composition(payload, submit_composition_child)
        except CreativeValidationError as exc:
            detail: dict[str, Any] = {"code": exc.code, "message": str(exc)}
            if exc.field is not None:
                detail["field"] = exc.field
            raise HTTPException(status_code=422, detail=detail) from exc
        except (ProfileResolutionError, ValueError, ValidationError) as exc:
            code = exc.code if isinstance(exc, ProfileResolutionError) else "workspace_request_rejected"
            raise HTTPException(status_code=422, detail={"code": code, "message": str(exc)[:300]}) from exc

    @app.get("/workspace-api/creative/compositions", include_in_schema=False)
    async def standalone_creative_compositions() -> dict[str, Any]:
        return {
            "items": [composition_projection(item) for item in store.list_creative_compositions()]
        }

    @app.get("/workspace-api/creative/compositions/{composition_id}", include_in_schema=False)
    async def standalone_creative_composition_get(composition_id: str) -> dict[str, Any]:
        try:
            return composition_projection(store.get_creative_composition(composition_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "creative_composition_not_found"}) from exc

    @app.patch("/workspace-api/creative/compositions/{composition_id}", include_in_schema=False)
    async def standalone_creative_composition_update(
        composition_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            reject_host_paths(payload)
            return recompose_creative_composition(composition_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "creative_composition_not_found"}) from exc
        except (ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "workspace_request_rejected", "message": str(exc)[:300]},
            ) from exc

    @app.delete("/workspace-api/creative/compositions/{composition_id}", include_in_schema=False)
    async def standalone_creative_composition_cancel(composition_id: str) -> dict[str, Any]:
        try:
            return await cancel_creative_composition(composition_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "creative_composition_not_found"}) from exc

    @app.post("/workspace-api/creative/validate", include_in_schema=False)
    async def standalone_creative_validate(payload: dict[str, Any]) -> dict[str, Any]:
        """Same-origin workspace bridge for standalone mode; not a public API contract."""
        try:
            reject_host_paths(payload)
            request = JobRequest.model_validate(payload.get("request"))
            creative_spec = CreativeSpec.model_validate(payload.get("creative_spec", {}))
            director_plan = (
                PromptPlan.model_validate(payload["director_plan"])
                if payload.get("director_plan") is not None else None
            )
            reference_context = accepted_reference_context(payload)
            profile_snapshot = manager.resolve_profiles(request)
            available_references = {
                item.asset_id for item in request.inputs
            } | set(profile_snapshot.get("reference_asset_ids", []))
            capability_value = await capability_document()
            return compile_creative(
                request,
                creative_spec,
                capabilities=capability_value["capabilities"],
                available_references=available_references,
                director_plan=director_plan,
                reference_context=reference_context,
            ).model_dump(mode="json")
        except CreativeValidationError as exc:
            detail: dict[str, Any] = {"code": exc.code, "message": str(exc)}
            if exc.field is not None:
                detail["field"] = exc.field
            raise HTTPException(status_code=422, detail=detail) from exc
        except ReferenceIntelligenceError as exc:
            raise HTTPException(
                status_code=422, detail={"code": exc.code, "message": str(exc)[:300]}
            ) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "asset_not_found"}) from exc
        except (ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "workspace_request_rejected", "message": str(exc)[:300]},
            ) from exc

    @app.post("/workspace-api/creative/direct", include_in_schema=False)
    async def standalone_creative_direct(payload: dict[str, Any]) -> dict[str, Any]:
        """Fail-soft standalone bridge: no Host identity means no text inference."""
        try:
            reject_host_paths(payload)
            creative_spec = CreativeSpec.model_validate(payload.get("creative_spec", {}))
            reference_context = accepted_reference_context(payload)
            directed = await creative_director.direct(
                None,
                str(payload.get("intent", "")),
                creative_spec.model_dump(mode="json"),
                mode=params_director_mode(payload),
                reference_context=reference_context,
            )
            return directed.model_dump(mode="json")
        except ReferenceIntelligenceError as exc:
            raise HTTPException(
                status_code=422, detail={"code": exc.code, "message": str(exc)[:300]}
            ) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "asset_not_found"}) from exc
        except (ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "workspace_request_rejected", "message": str(exc)[:300]},
            ) from exc

    @app.post("/workspace-api/references/analyze", include_in_schema=False)
    async def standalone_reference_analyze(payload: dict[str, Any]) -> dict[str, Any]:
        """Deterministic standalone analysis; semantic Vision requires Host identity."""
        try:
            reject_host_paths(payload)
            return await analyze_reference(payload, None)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "asset_not_found"}) from exc
        except ReferenceIntelligenceError as exc:
            raise HTTPException(
                status_code=422, detail={"code": exc.code, "message": str(exc)[:300]}
            ) from exc
        except (ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "workspace_request_rejected", "message": str(exc)[:300]},
            ) from exc

    @app.post("/workspace-api/creative/evaluate", include_in_schema=False)
    async def standalone_creative_evaluate(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            reject_host_paths(payload)
            return await evaluate_creative_candidates(payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "asset_not_found"}) from exc
        except CreativeEvaluationError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.code, "message": str(exc)[:300]},
            ) from exc
        except (ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "workspace_request_rejected", "message": str(exc)[:300]},
            ) from exc

    @app.get("/")
    @app.get("/create")
    @app.get("/library")
    @app.get("/activity")
    @app.get("/jobs")
    @app.get("/models")
    @app.get("/profiles")
    @app.get("/settings")
    async def workspace() -> HTMLResponse:
        nonlocal workspace_test_delay_pending
        delay_sec = workspace_test_response_delay_sec() if workspace_test_delay_pending else 0.0
        workspace_test_delay_pending = False
        if delay_sec:
            await asyncio.sleep(delay_sec)
        html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
        stylesheet = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")
        script = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")
        creative_templates = json.dumps(
            creative_compiler.catalog.public_document(), ensure_ascii=False, separators=(",", ":")
        ).replace("</", "<\\/")
        envelope = size_envelope()
        workspace_config = json.dumps(
            {"envelope": envelope, "presets": size_presets(envelope)},
            ensure_ascii=False,
            separators=(",", ":"),
        ).replace("</", "<\\/")
        html = html.replace("<!-- MEDIA_FORGE_INLINE_STYLE -->", f"<style>{stylesheet}</style>")
        html = html.replace(
            "<!-- MEDIA_FORGE_WORKSPACE_CONFIG -->",
            f'<script type="application/json" id="workspace-config-data">{workspace_config}</script>',
        )
        html = html.replace(
            "<!-- MEDIA_FORGE_CREATIVE_TEMPLATES -->",
            f'<script type="application/json" id="creative-template-data">{creative_templates}</script>',
        )
        html = html.replace("<!-- MEDIA_FORGE_INLINE_SCRIPT -->", f"<script>{script}</script>")
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    return app


app = create_app()
