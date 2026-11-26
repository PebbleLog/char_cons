"""本地性能冒烟（Mock Provider）。

注意：这些数值只反映本地代码、SQLite 与 Mock 服务的开销，
不能代表真实豆包/Seedream 的时延。真实性能目标 180/60/180/180 秒
必须在获得凭据后通过 scripts/verify_performance.py 实测。
"""

from __future__ import annotations

import time

import pytest

from app.providers.mock import MockVisionProvider
from tests.test_generation_loop import _start_generation
from tests.test_report import FixedProvider, _analyze_and_wait, _create_task


@pytest.fixture
def csrf(client):
    token = client.get("/api/session").json()["csrfToken"]
    return {"X-CSRF-Token": token}


def test_local_pipeline_performance_observation(client, csrf, app):
    task = _create_task(client, csrf)
    app.state.vision_provider_factory = lambda _settings: FixedProvider()

    started = time.perf_counter()
    status = _analyze_and_wait(client, csrf, task["id"])
    analysis_seconds = time.perf_counter() - started
    assert status["status"] == "completed"
    assert analysis_seconds < 15, analysis_seconds

    started = time.perf_counter()
    state = _start_generation(client, csrf, task["id"], "ISS-002")
    generation_seconds = time.perf_counter() - started
    assert state["generation"]["status"] == "succeeded"
    assert generation_seconds < 20, generation_seconds

    started = time.perf_counter()
    report = client.get(f"/api/tasks/{task['id']}/report")
    report_seconds = time.perf_counter() - started
    assert report.status_code == 200
    assert report_seconds < 2, report_seconds

    started = time.perf_counter()
    export = client.get(f"/api/tasks/{task['id']}/export?format=json")
    export_seconds = time.perf_counter() - started
    assert export.status_code == 200
    assert export_seconds < 2, export_seconds

    print(
        "\n[perf-mock] "
        f"analysis(3 shots)={analysis_seconds:.3f}s "
        f"generation(4 candidates)={generation_seconds:.3f}s "
        f"report={report_seconds:.3f}s export={export_seconds:.3f}s"
    )
