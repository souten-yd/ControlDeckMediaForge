"""生成後に model を載せたまま次の依頼を待つ。

載せ直しは実測で十数秒かかり、続けて頼まれる場面では待ち時間のほとんどを占める。
一方、抱えてよいのは他が GPU を要らない間だけである。lease を持ったまま待つのは、
抱えている VRAM を broker から見えるようにしておくためで、返して待つと
「空いている」ことになり、その上へ LLM が載って単一 GPU では入らない。
"""

from __future__ import annotations

import inspect
from pathlib import Path

from mediaforge.domain import Job, JobRequest, JobStatus
from mediaforge.host.jobs import HostExecution
from mediaforge.jobs import JobManager
from mediaforge.store import Store, utc_now


class _Process:
    returncode = None


def _manager(tmp_path: Path, *, linger: float = 90.0) -> JobManager:
    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(store, warm_linger_sec=linger)
    manager.host_client = object()  # type: ignore[assignment]
    manager._warm_worker = (_Process(), ("a", "b", "c", "d"))  # type: ignore[assignment]
    return manager


def _execution(device_id: str | None, lease_id: str | None = "lease_1") -> HostExecution:
    value = HostExecution(
        identity=None,  # type: ignore[arg-type]
        host_job_id="job_1",
        workload_class="interactive",
        owns_terminal=False,
    )
    value.device_id = device_id
    value.lease_id = lease_id
    return value


def _job(*, semantic: bool = False) -> Job:
    request = JobRequest.model_validate({
        "operation": "image.generate",
        "intent": "a blue ceramic mug",
        "qa": {"deterministic": True, "semantic": semantic, "max_regeneration_attempts": 0},
    })
    now = utc_now()
    return Job(
        id="job_1",
        status=JobStatus.RUNNING,
        progress=0.0,
        request=request,
        created_at=now,
        updated_at=now,
    )


def test_a_gpu_generation_keeps_its_model_loaded(tmp_path: Path):
    manager = _manager(tmp_path)
    assert manager._can_linger(_job(), _execution("gpu0")) is True


def test_ram_execution_is_not_worth_holding(tmp_path: Path):
    """host 配置を抱えても次が速くならない。空けたほうがよい。"""
    manager = _manager(tmp_path)
    assert manager._can_linger(_job(), _execution("host")) is False


def test_semantic_review_needs_the_gpu_right_away(tmp_path: Path):
    """直後に Host が VLM を載せる。抱えたままでは単一 GPU に入らない。"""
    manager = _manager(tmp_path)
    assert manager._can_linger(_job(semantic=True), _execution("gpu0")) is False


def test_a_job_without_a_lease_holds_nothing(tmp_path: Path):
    manager = _manager(tmp_path)
    assert manager._can_linger(_job(), _execution("gpu0", lease_id=None)) is False


def test_zero_linger_restores_the_previous_behaviour(tmp_path: Path):
    manager = _manager(tmp_path, linger=0.0)
    assert manager._can_linger(_job(), _execution("gpu0")) is False


def test_a_retired_worker_leaves_nothing_to_hold(tmp_path: Path):
    manager = _manager(tmp_path)
    manager._warm_worker = None
    assert manager._can_linger(_job(), _execution("gpu0")) is False


def test_the_next_job_keeps_the_model_but_gives_the_lease_back(tmp_path: Path):
    """待ちをやめるとき model まで降ろしたら、待った意味が無い。

    lease は返す。次の job は自分の lease を取るので、同じ device に 2 つは要らない。
    """
    source = inspect.getsource(JobManager._run_one)
    assert "_end_linger(retire=False)" in source


def test_a_lingering_lease_is_not_released_by_the_job_that_handed_it_over(tmp_path: Path):
    """返してしまうと、抱えている VRAM が broker から見えなくなる。"""
    source = inspect.getsource(JobManager._execute)
    assert "execution is not self._linger_execution" in source


def test_shutdown_gives_the_device_back(tmp_path: Path):
    source = inspect.getsource(JobManager.stop)
    assert "_end_linger(retire=True)" in source


def test_it_is_off_until_the_host_can_account_for_a_held_model(tmp_path: Path):
    """既定では抱えない。

    ControlDeck の受付は「実際に使われている VRAM」で空きを見る。lease を返した
    後も model が載っていると、次の生成が入れないと判断されて待ち続ける
    （実測: 2 枚目が 300 秒待って失効）。lease を持ったまま待てば場所は説明できる
    が、次の生成は自分の lease を取るので同じ device に 2 つは持てない。
    """
    import dataclasses

    from mediaforge.config import Settings

    field = {item.name: item for item in dataclasses.fields(Settings)}["warm_linger_sec"]
    assert field.default == 0.0
