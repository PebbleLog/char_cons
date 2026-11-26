"""可重复的 Playwright 页面回归（本机 Chrome/Edge）。

覆盖：七页导航、历史真实任务、结果页、建议/抽卡、生成闭环、采用/复检、
Markdown/JSON 下载、设置连接测试与配置弹窗、历史搜索/筛选、375/1440 布局。

使用 Mock 生成与受控视觉观察，不调用真实模型。运行：
    D:\\miniconda3\\miniconda3\\envs\\Agent\\python.exe scripts\\e2e_playwright.py
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.helpers import make_image  # noqa: E402

SCREENS = ("home", "create", "analysis", "results", "optimizer", "history", "settings")
PROFILE = (
    "阿岚，深棕长发低侧发髻，浅米色亚麻西装外套，黑色丝质衬衫，紫色口袋巾，"
    "圆形吊坠项链（蓝紫四瓣花）。"
)
SCRIPT = "这些镜头为同一场戏的连续动作，无换装情节。"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_health(base: str, process: subprocess.Popen, timeout: float = 40.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("E2E 服务器提前退出")
        try:
            if httpx.get(f"{base}/api/health", timeout=2.0).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise RuntimeError("E2E 服务器启动超时")


def launch_browser(playwright) -> Browser:
    last_error = None
    for channel in ("chrome", "msedge"):
        try:
            return playwright.chromium.launch(channel=channel, headless=True)
        except Exception as exc:  # 未安装对应浏览器
            last_error = exc
    raise RuntimeError(f"无法启动 Chrome/Edge：{last_error}")


def create_task(base: str) -> str:
    with httpx.Client(base_url=base, timeout=30.0) as client:
        csrf = client.get("/api/session").json()["csrfToken"]
        headers = {"X-CSRF-Token": csrf, "Origin": base}
        task = client.post(
            "/api/tasks",
            json={
                "name": "阿岚 · E2E 回归",
                "characterName": "阿岚",
                "profileRaw": PROFILE,
                "scriptRaw": SCRIPT,
                "defaultBatchSize": 4,
            },
            headers=headers,
        )
        task.raise_for_status()
        task_id = task.json()["id"]
        files = [
            (
                "files",
                (f"shot{i}.png", make_image(base=(200 - i * 10, 185, 165)), "image/png"),
            )
            for i in range(1, 4)
        ]
        upload = client.post(f"/api/tasks/{task_id}/shots", files=files, headers=headers)
        upload.raise_for_status()
        analyze = client.post(f"/api/tasks/{task_id}/analyze", headers=headers)
        analyze.raise_for_status()
        deadline = time.time() + 20
        while time.time() < deadline:
            status = client.get(f"/api/tasks/{task_id}/analysis").json()
            if status["status"] in {"completed", "partial", "failed"}:
                assert status["status"] == "completed", status
                return task_id
            time.sleep(0.1)
        raise RuntimeError("E2E 分析超时")


def main() -> int:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    console_errors: list[str] = []
    page_errors: list[str] = []
    checks: list[str] = []

    with tempfile.TemporaryDirectory(prefix="char_cons_e2e_") as home:
        env = {
            **os.environ,
            "CHAR_CONS_HOME": home,
            "CHAR_CONS_ANALYSIS_PROVIDER": "mock",
            "CHAR_CONS_ANALYSIS_MODEL": "mock-vision",
            "CHAR_CONS_GENERATION_PROVIDER": "mock",
            "CHAR_CONS_GENERATION_MODEL": "mock-seedream",
        }
        process = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "--app-dir", "scripts",
                "e2e_app:app", "--host", "127.0.0.1", "--port", str(port),
                "--log-level", "warning",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            wait_health(base, process)
            task_id = create_task(base)
            checks.append("backend analysis + report fixture")

            with sync_playwright() as playwright:
                browser = launch_browser(playwright)
                context = browser.new_context(viewport={"width": 1440, "height": 900})
                page = context.new_page()
                page.on(
                    "console",
                    lambda message: console_errors.append(message.text)
                    if message.type == "error"
                    else None,
                )
                page.on("pageerror", lambda error: page_errors.append(str(error)))

                page.goto(f"{base}/#history", wait_until="domcontentloaded")
                page.wait_for_function("window.__CCS && window.__CCS.STATE")
                row = page.locator(f'button.history-row[data-task-id="{task_id}"]')
                row.wait_for(timeout=10000)
                checks.append("history task row")

                row.click()
                page.wait_for_url(re.compile(r"#results$"))
                page.wait_for_function(
                    "document.querySelector('#sum-issues')?.textContent === '2'"
                )
                assert page.locator('#matrix-body .cell-btn.is-focused').count() == 0
                assert page.locator('#issue-list .issue-card.is-selected').count() == 0

                # 刷新检测结果页必须恢复真实报告，而不是退回原型演示数据
                page.reload(wait_until="domcontentloaded")
                page.wait_for_function(
                    "document.querySelector('#sum-issues')?.textContent === '2'",
                    timeout=20000,
                )
                assert page.locator("#screen-results").is_visible()
                checks.append("results refresh restore")

                page.locator('#screen-results .tab[data-tab="suggestions"]').click()
                page.wait_for_function(
                    "document.querySelectorAll('#suggestion-grid .suggestion-card').length === 2"
                )
                checks.append("real report + suggestions")

                page.locator("#suggestion-grid .suggestion-card").nth(1).locator(
                    "button[data-real-optimize]"
                ).click()
                page.wait_for_url(re.compile(r"#optimizer$"))
                page.wait_for_function(
                    "document.querySelector('#opt-title')?.textContent.includes('S3')"
                    " && document.querySelector('#opt-title')?.textContent.includes('本镜头')"
                )
                page.wait_for_function(
                    "document.querySelector('#opt-shot-switch .is-active')?.textContent.includes('问题')"
                )
                checks.append("optimizer real data")

                # 刷新优化页必须恢复真实任务，而不是退回原型演示数据
                page.reload(wait_until="domcontentloaded")
                page.wait_for_function(
                    "document.querySelector('#opt-prompt')?.value.startsWith('保持当前镜头原构图')",
                    timeout=20000,
                )
                assert page.locator("#opt-original-img").get_attribute("src").startswith(
                    "/api/tasks/"
                )
                checks.append("optimizer refresh restore")

                page.locator("#opt-generate").click()
                page.locator("#modal-backdrop").wait_for(state="visible")
                assert "第三方服务调用告知" in page.locator("#modal-title").inner_text()
                page.locator("#modal-confirm").click()
                page.wait_for_function(
                    "document.querySelectorAll('#opt-candidates .candidate-card').length === 4",
                    timeout=20000,
                )
                page.wait_for_function(
                    "!document.querySelector('#opt-adopt')?.disabled"
                    " && document.querySelector('#opt-adopt')?.textContent.includes('采用为当前镜头')",
                    timeout=20000,
                )
                checks.append("generation + precheck + privacy notice")

                page.locator("#opt-adopt").click()
                page.wait_for_function(
                    "document.querySelector('#opt-adopt')?.textContent.includes('查看更新后的报告')",
                    timeout=20000,
                )
                page.locator("#opt-adopt").click()
                page.wait_for_url(re.compile(r"#results$"))
                page.wait_for_function(
                    "document.querySelector('#sum-issues')?.textContent === '1'"
                )
                page.wait_for_function(
                    "document.querySelector('#results-gallery [data-real-gallery=\"S3\"] .gallery-copy')"
                    "?.textContent.includes('当前版本')"
                )
                page.locator('#results-gallery [data-real-gallery="S3"]').click()
                page.wait_for_function(
                    "document.querySelector('#results-inspector')?.textContent.includes('查看原图')"
                )
                checks.append("adoption + single-shot recheck + report refresh")

                with page.expect_download() as md_info:
                    page.locator('#screen-results [data-export="md"]').click()
                md_path = md_info.value.path()
                markdown = Path(md_path).read_text(encoding="utf-8")
                assert "# 角色形象一致性检查报告" in markdown
                assert "GEN-001" in markdown
                assert "sk-" not in markdown
                with page.expect_download() as json_info:
                    page.locator('#screen-results [data-export="json"]').click()
                json_path = json_info.value.path()
                payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
                assert payload["stats"]["confirmedIssues"] == 1
                assert len(payload["generationRecords"]) == 1
                assert len(payload["adoptions"]) == 1
                checks.append("markdown/json downloads")

                page.goto(f"{base}/#settings", wait_until="domcontentloaded")
                page.wait_for_function(
                    "document.querySelector('#settings-report-stats')?.textContent.includes('1 条任务记录')",
                    timeout=10000,
                )
                page.locator("#screen-settings [data-action='test-analysis']").click()
                page.wait_for_function(
                    "document.querySelector('#test-analysis-result')?.textContent.includes('连接成功')",
                    timeout=10000,
                )
                page.locator("#analysis-config-btn").click()
                page.locator("#service-config-form").wait_for(state="visible")
                assert page.locator("#config-provider").input_value() == "mock"
                page.locator("#modal-backdrop .btn-ghost[data-action='close-modal']").click()
                page.locator("#batch-seg [data-count='2']").click()
                page.wait_for_function(
                    "document.querySelector('#batch-seg .is-active')?.dataset.count === '2'"
                )
                page.locator("#upload-limit-btn").click()
                page.locator("#limit-config-form").wait_for(state="visible")
                page.locator("#limit-upload").fill("25")
                page.locator("#modal-confirm").click()
                page.wait_for_function(
                    "document.querySelector('#upload-limit-btn')?.textContent.includes('25 MB')"
                )
                checks.append("settings status/test/config/limits")

                page.goto(f"{base}/#history", wait_until="domcontentloaded")
                page.wait_for_function(
                    f"document.querySelector('button.history-row[data-task-id=\"{task_id}\"]')"
                )
                page.locator("#history-search").fill("不存在的角色")
                page.wait_for_function(
                    "!document.querySelector('#history-empty')?.hidden"
                )
                page.locator("#history-search").fill("")
                page.locator('#history-filters [data-filter="failed"]').click()
                page.wait_for_function(
                    "Array.from(document.querySelectorAll('#history-rows .history-row')).every(r => r.hidden)"
                )
                page.locator('#history-filters [data-filter="all"]').click()
                checks.append("history search/filter")

                page.set_viewport_size({"width": 375, "height": 812})
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= window.innerWidth"
                )
                page.goto(f"{base}/#settings", wait_until="domcontentloaded")
                page.wait_for_function("window.__CCS")
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= window.innerWidth"
                )
                checks.append("375px layout")

                page.set_viewport_size({"width": 1440, "height": 900})
                for screen in SCREENS:
                    page.goto(f"{base}/#{screen}", wait_until="domcontentloaded")
                    page.wait_for_function("window.__CCS")
                    page.wait_for_selector(f"#screen-{screen}.is-active", timeout=5000)
                checks.append("7 screens reachable")

                with tempfile.TemporaryDirectory(prefix="char_cons_e2e_media_") as media:
                    media_paths = []
                    for index in range(1, 4):
                        path = Path(media) / f"ui-shot-{index}.png"
                        path.write_bytes(make_image(base=(200 - index * 8, 185, 165)))
                        media_paths.append(str(path))
                    page.goto(f"{base}/#create", wait_until="domcontentloaded")
                    page.wait_for_function("window.__CCS")
                    assert page.locator("#character-input").input_value() == ""
                    assert page.locator("#shot-list .shot-card").count() == 0
                    page.locator("#character-input").fill(PROFILE)
                    page.locator("#shot-input").set_input_files(media_paths)
                    page.wait_for_function(
                        "document.querySelectorAll('#shot-list .shot-card').length === 3",
                        timeout=10000,
                    )
                    page.locator("#start-analysis").click()
                    page.wait_for_url(re.compile(r"#analysis$"), timeout=20000)
                    page.wait_for_function(
                        "document.querySelector('#analysis-status-text')?.textContent.includes('真实任务')",
                        timeout=20000,
                    )
                    # 分析页接管镜头后，返回新建页仍需保留本地文件，可直接再次开始检查。
                    page.wait_for_function(
                        """() => {
                            const shots = window.__CCS?.STATE?.shots || [];
                            return shots.length === 3 && shots.every((shot) => shot.nativeFile);
                        }""",
                        timeout=20000,
                    )
                    page.locator('.nav-item[data-nav="create"]').first.click()
                    page.wait_for_selector("#screen-create.is-active", timeout=5000)
                    assert page.locator("#shot-list .shot-card").count() == 3
                    assert page.locator("#start-analysis").is_enabled()
                    deadline = time.time() + 20
                    total = 0
                    while time.time() < deadline:
                        total = httpx.get(f"{base}/api/tasks", timeout=5.0).json()["total"]
                        if total >= 2:
                            break
                        time.sleep(0.3)
                    assert total >= 2, total
                checks.append("create page upload + auto start analysis + real analysis page")

                browser.close()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

    assert not page_errors, f"页面 JS 异常：{page_errors}"
    assert not console_errors, f"控制台错误：{console_errors}"
    print("E2E 页面回归通过")
    for item in checks:
        print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
