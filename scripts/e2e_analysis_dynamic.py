"""检测任务动态过程回归：真实页面 + 脚本化状态推进。

验证目标：
1. 观察中不出现写死的 0 / 11，显示实时计时与真实完成数；
2. 判定 / 生成建议阶段不重建观察项与流水线节点（无闪动）；
3. 轮询更新不改写 AI 分析面板的滚动位置（不自动滚动）；
4. 生成建议阶段显示真实的「已整理 N / M 条」；
5. 1440 / 375 宽度可用。

运行：
    D:\\miniconda3\\miniconda3\\envs\\Agent\\python.exe scripts\\e2e_analysis_dynamic.py
"""

from __future__ import annotations

import copy
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.helpers import make_image  # noqa: E402

PROFILE = (
    "阿岚，深棕长发低侧发髻，浅米色亚麻西装外套，黑色丝质衬衫，紫色口袋巾，"
    "圆形吊坠项链（蓝紫四瓣花）。"
)
SCRIPT = "这些镜头为同一场戏的连续动作，无换装情节。"

STAGES = ["素材校验", "设定解析", "剧本解析", "逐镜头观察", "一致性判定", "生成建议"]


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


def create_completed_task(base: str) -> tuple[str, dict]:
    with httpx.Client(base_url=base, timeout=30.0) as client:
        csrf = client.get("/api/session").json()["csrfToken"]
        headers = {"X-CSRF-Token": csrf, "Origin": base}
        task = client.post(
            "/api/tasks",
            json={
                "name": "阿岚 · 动态回归",
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
            ("files", (f"shot{i}.png", make_image(base=(200 - i * 10, 185, 165)), "image/png"))
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
                return task_id, status
            time.sleep(0.1)
        raise RuntimeError("E2E 分析超时")


def build_timeline(real: dict) -> list[dict]:
    """把已完成任务的真实数据拆成逐阶段状态，模拟运行中的动态过程。"""
    total_suggestions = int(real.get("suggestions", {}).get("total", 0))
    timeline: list[dict] = []

    def base_status(progress: int, stage_index: int, **overrides) -> dict:
        status = copy.deepcopy(real)
        status.update(
            {
                "status": "running",
                "progress": progress,
                "etaSeconds": None,
                "stage": {
                    "index": stage_index,
                    "name": STAGES[stage_index - 1],
                    "completed": False,
                },
                "stages": [
                    {"index": index + 1, "name": name}
                    for index, name in enumerate(STAGES)
                ],
                "suggestions": {"ready": 0, "total": total_suggestions},
                "currentShot": None,
                "error": None,
            }
        )
        status.update(overrides)
        return status

    def shots_with(analyzing: list[str], done: list[str], judged: bool) -> list[dict]:
        shots = []
        for shot in copy.deepcopy(real["shots"]):
            code = shot["shotCode"]
            if code in analyzing:
                shot["analysisStatus"] = "analyzing"
                shot["judged"] = False
                shot["verdicts"] = {}
                shot["inconsistent"] = 0
                shot["unknown"] = 0
            elif code in done:
                shot["analysisStatus"] = "ok"
                shot["judged"] = judged
                if not judged:
                    shot["verdicts"] = {}
                    shot["inconsistent"] = 0
                    shot["unknown"] = 0
            else:
                shot["analysisStatus"] = "pending"
                shot["judged"] = False
                shot["verdicts"] = {}
                shot["inconsistent"] = 0
                shot["unknown"] = 0
            shots.append(shot)
        return shots

    timeline.append(
        base_status(
            25,
            4,
            etaSeconds=60,
            shots=shots_with(["S1", "S2", "S3"], [], False),
        )
    )
    timeline.append(
        base_status(
            49,
            4,
            etaSeconds=40,
            shots=shots_with(["S2", "S3"], ["S1"], False),
        )
    )
    timeline.append(
        base_status(
            73,
            4,
            etaSeconds=20,
            shots=shots_with(["S3"], ["S1", "S2"], False),
        )
    )
    timeline.append(
        base_status(
            92,
            5,
            etaSeconds=None,
            shots=shots_with([], ["S1", "S2", "S3"], False),
        )
    )
    timeline.append(
        base_status(
            95,
            6,
            shots=shots_with([], ["S1", "S2", "S3"], True),
            suggestions={"ready": 0, "total": total_suggestions},
        )
    )
    timeline.append(
        base_status(
            97,
            6,
            shots=shots_with([], ["S1", "S2", "S3"], True),
            suggestions={"ready": 1, "total": total_suggestions},
        )
    )
    timeline.append(
        base_status(
            98,
            6,
            shots=shots_with([], ["S1", "S2", "S3"], True),
            suggestions={"ready": total_suggestions, "total": total_suggestions},
        )
    )
    # 重复两个运行中状态，用于验证用户选择镜头后跨轮询保持。
    for _ in range(2):
        timeline.append(
            base_status(
                98,
                6,
                shots=shots_with([], ["S1", "S2", "S3"], True),
                suggestions={"ready": total_suggestions, "total": total_suggestions},
            )
        )
    done = copy.deepcopy(real)
    done["progress"] = 100
    timeline.append(done)
    return timeline


def install_instrumentation(page: Page) -> None:
    page.evaluate(
        """() => {
            window.__dyn = { added: 0, removed: 0, scrollCount: 0 };
            const list = document.querySelector('#analysis-insights .obs-list');
            const pipeline = document.querySelector('#analysis-pipeline');
            window.__obsProbe = list.querySelector('.obs-item');
            window.__pipeProbe = pipeline.querySelector('.pipe-step');
            const count = (records) => records.forEach((record) => {
                record.removedNodes.forEach((node) => {
                    if (node.nodeType === 1 && (node.classList.contains('obs-item') || node.classList.contains('pipe-step'))) {
                        window.__dyn.removed += 1;
                    }
                });
                record.addedNodes.forEach((node) => {
                    if (node.nodeType === 1 && (node.classList.contains('obs-item') || node.classList.contains('pipe-step'))) {
                        window.__dyn.added += 1;
                    }
                });
            });
            new MutationObserver(count).observe(list, { childList: true });
            new MutationObserver(count).observe(pipeline, { childList: true });
            const body = document.querySelector('.analysis-insights .insight-body');
            body.addEventListener('scroll', () => { window.__dyn.scrollCount += 1; });
            body.scrollTop = 90;
            setTimeout(() => {
                window.__dyn.scrollStart = body.scrollTop;
                window.__dyn.scrollCount = 0;
            }, 120);
        }"""
    )


def read_dyn(page: Page) -> dict:
    return page.evaluate(
        """() => {
            const body = document.querySelector('.analysis-insights .insight-body');
            return {
                added: window.__dyn.added,
                removed: window.__dyn.removed,
                scrollCount: window.__dyn.scrollCount,
                scrollStart: window.__dyn.scrollStart,
                scrollTop: body.scrollTop,
                sameObs: window.__obsProbe.isSameNode(document.querySelector('#analysis-insights .obs-item')),
                samePipe: window.__pipeProbe.isSameNode(document.querySelector('#analysis-pipeline .pipe-step')),
            };
        }"""
    )


def wait_text(page: Page, selector: str, expected: str, timeout: int = 15000) -> None:
    page.wait_for_function(
        """([selector, expected]) => document.querySelector(selector)?.textContent.includes(expected)""",
        arg=[selector, expected],
        timeout=timeout,
    )


def main() -> int:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    checks: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    artifacts = Path(tempfile.mkdtemp(prefix="char_cons_dynamic_"))

    with tempfile.TemporaryDirectory(prefix="char_cons_home_") as home:
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
                sys.executable,
                "-m",
                "uvicorn",
                "--app-dir",
                "scripts",
                "e2e_app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            wait_health(base, process)
            task_id, real_status = create_completed_task(base)
            timeline = build_timeline(real_status)
            cursor = {"index": 0}

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 900})
                context.add_init_script(
                    "try { sessionStorage.setItem('char_cons_active_analysis', "
                    f"{json.dumps(json.dumps({'taskId': task_id, 'taskName': '阿岚 · 动态回归'}))}"
                    "); } catch (error) { /* 初始空白页可能不可用 */ }"
                )
                page = context.new_page()
                page.on(
                    "console",
                    lambda message: console_errors.append(message.text)
                    if message.type == "error"
                    else None,
                )
                page.on("pageerror", lambda error: page_errors.append(str(error)))

                def serve_status(route):
                    index = min(cursor["index"], len(timeline) - 1)
                    cursor["index"] += 1
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(timeline[index], ensure_ascii=False),
                    )

                page.route(f"**/api/tasks/{task_id}/analysis", serve_status)
                page.goto(f"{base}/#analysis", wait_until="domcontentloaded")
                page.wait_for_function("window.__CCS && window.__CCS.STATE")
                page.wait_for_selector("#analysis-shot-list .rail-item", timeout=15000)

                # 步骤 1：全部观察中
                wait_text(page, "#analysis-subline", "逐镜头观察", 15000)
                wait_text(page, "#analysis-subline", "已用时")
                assert "0 / 11" not in page.locator("#analysis-insights").inner_text()
                assert "观察中" in page.locator("#analysis-insights").inner_text()
                assert page.locator(".rail-item.is-analyzing").count() == 3
                wait_text(page, "#task-status-pill", "分析中")
                page.screenshot(path=str(artifacts / "step1_observing_1440.png"))
                clock_before = page.locator("#analysis-elapsed").inner_text()
                page.wait_for_timeout(1500)
                clock_after = page.locator("#analysis-elapsed").inner_text()
                assert clock_before != clock_after, (clock_before, clock_after)
                checks.append("观察中：无 0/11，显示实时计时与观察中状态")

                # 步骤 2：S1 完成，出现真实 11 / 11
                wait_text(page, "#analysis-subline", "已完成 1 / 3", 15000)
                wait_text(page, "#analysis-insights", "11 / 11", 15000)
                wait_text(page, '[data-role="subject-name"]', "当前镜头主体", 15000)
                wait_text(page, '[data-role="subject-meta"]', "单人画面", 15000)
                subject_text = page.locator('[data-role="subject-card"]').inner_text()
                assert "阿岚" not in subject_text
                assert "%" not in subject_text and not any(ch.isdigit() for ch in subject_text)
                page.screenshot(path=str(artifacts / "step2_first_shot_done_1440.png"))
                checks.append("S1 完成：观察数来自真实数据 11 / 11")

                # 步骤 3：全部观察完成，等待判定
                wait_text(page, "#rail-count", "已完成 3 / 3", 15000)
                wait_text(page, "#analysis-subline", "已比对", 15000)
                wait_text(page, '[data-role="footer"]', "等待一致性判定", 15000)
                wait_text(page, "#analysis-stage-label", "一致性判定", 15000)
                install_instrumentation(page)
                page.screenshot(path=str(artifacts / "step3_judging_1440.png"))
                checks.append("全部观察完成：进入一致性判定")

                # 步骤 4：生成建议，显示真实建议条数
                wait_text(page, "#analysis-subline", "生成建议", 15000)
                wait_text(page, "#analysis-subline", "已整理 0 /", 15000)
                wait_text(page, "#analysis-stage-label", "生成建议", 15000)
                page.wait_for_function(
                    """() => {
                        const pills = [...document.querySelectorAll(
                            '#analysis-insights .obs-verdict .status-pill'
                        )];
                        return pills.length === 11
                            && pills.every((pill) => !pill.textContent.includes('待判定'));
                    }""",
                    timeout=15000,
                )
                page.screenshot(path=str(artifacts / "step4_suggestions_start_1440.png"))
                checks.append("生成建议：显示建议子进度而非写死 99%")

                # 步骤 5：建议推进到 1 / 2
                wait_text(page, "#analysis-subline", "已整理 1 /", 15000)
                page.wait_for_timeout(2600)
                # 点击当前镜头 S1（索引 0）后，跨轮询必须保持选择，不能跳回 S3。
                page.locator(".rail-item").nth(0).click()
                page.wait_for_timeout(2600)
                assert page.locator(".rail-item.is-active b").inner_text().strip() == "S1"
                wait_text(page, '[data-role="obs-title"]', "OBSERVATIONS · S1", 15000)
                dyn = read_dyn(page)
                assert dyn["added"] == 0 and dyn["removed"] == 0, dyn
                assert dyn["sameObs"] and dyn["samePipe"], dyn
                assert dyn["scrollCount"] == 0, dyn
                assert dyn["scrollTop"] == dyn["scrollStart"], dyn
                checks.append("轮询推进：节点复用、无重建、无自动滚动、镜头选择保持")

                # 步骤 6：完成（运行状态卡收起，状态由标题与阶段信息统一表达）
                wait_text(page, "#analysis-subline", "分析完成", 15000)
                page.wait_for_function(
                    "() => document.querySelector('#analysis-run-card')?.hidden === true",
                    timeout=15000,
                )
                wait_text(page, "#task-status-pill", "已完成", 15000)
                wait_text(page, "#analysis-result-text", "处确定不一致", 15000)
                assert page.locator("#analysis-result-cta").is_visible()
                wait_text(page, "#analysis-subline", "用时")
                page.screenshot(path=str(artifacts / "step6_complete_1440.png"))
                checks.append("完成：统计与状态均来自真实结果")

                dyn_final = read_dyn(page)
                assert dyn_final["added"] == 0 and dyn_final["removed"] == 0, dyn_final
                assert dyn_final["scrollCount"] == 0, dyn_final
                assert dyn_final["scrollTop"] == dyn_final["scrollStart"], dyn_final
                checks.append("完成阶段：仍无节点重建与滚动跳动")

                # 切换到 S2，验证真实「不一致」判定与目标文案。
                page.locator(".rail-item").nth(1).click()
                wait_text(page, '[data-role="obs-title"]', "OBSERVATIONS · S2", 15000)
                page.wait_for_function(
                    """() => [...document.querySelectorAll(
                        '#analysis-insights .obs-verdict .status-pill'
                    )].some((pill) => pill.textContent.includes('不一致'))""",
                    timeout=15000,
                )
                assert "与设定不符" in page.locator("#analysis-insights").inner_text()
                page.locator(".rail-item").nth(0).click()
                wait_text(page, '[data-role="obs-title"]', "OBSERVATIONS · S1", 15000)
                checks.append("判定结果按真实 verdict 渲染（一致 / 仅记录 / 不一致）")

                # 375 宽度
                page.set_viewport_size({"width": 375, "height": 812})
                page.wait_for_timeout(400)
                overflow = page.evaluate(
                    "() => document.documentElement.scrollWidth - window.innerWidth"
                )
                assert overflow <= 1, overflow
                assert page.locator("#screen-analysis").is_visible()
                page.screenshot(path=str(artifacts / "step6_complete_375.png"), full_page=True)
                checks.append("375 宽度：无横向溢出")

                assert not console_errors, console_errors
                assert not page_errors, page_errors
                checks.append("无控制台 / 页面脚本错误")

                # 直接打开 #analysis（无已保存任务）不得伪造演示分析。
                empty_context = browser.new_context(viewport={"width": 1440, "height": 900})
                empty_page = empty_context.new_page()
                empty_page.goto(f"{base}/#analysis", wait_until="domcontentloaded")
                empty_page.wait_for_function("window.__CCS && window.__CCS.STATE")
                empty_page.wait_for_timeout(800)
                assert empty_page.evaluate("window.__CCS.STATE.analysis.started") is False
                assert "正在连接分析任务" in empty_page.locator("#analysis-subline").inner_text()
                assert empty_page.locator("#rail-count").inner_text().strip() == "已完成 — / —"
                empty_context.close()
                checks.append("无任务直接打开 #analysis：保持中性空状态，不伪造分析")

                def open_state_page(payload: dict):
                    state_context = browser.new_context(
                        viewport={"width": 1440, "height": 900}
                    )
                    state_context.add_init_script(
                        "try { sessionStorage.setItem('char_cons_active_analysis', "
                        f"{json.dumps(json.dumps({'taskId': task_id, 'taskName': '阿岚 · 动态回归'}))}"
                        "); } catch (error) { /* ignore */ }"
                    )
                    state_page = state_context.new_page()
                    state_page.route(
                        f"**/api/tasks/{task_id}/analysis",
                        lambda route: route.fulfill(
                            status=200,
                            content_type="application/json",
                            body=json.dumps(payload, ensure_ascii=False),
                        ),
                    )
                    state_page.goto(f"{base}/#analysis", wait_until="domcontentloaded")
                    state_page.wait_for_function("window.__CCS && window.__CCS.STATE")
                    return state_context, state_page

                # 服务重启后的 paused：在途镜头不得永久转圈，也不得谎报“镜头失败”。
                paused = copy.deepcopy(real_status)
                paused.update(
                    {
                        "status": "paused",
                        "progress": 90,
                        "etaSeconds": None,
                        "stage": {"index": 4, "name": "逐镜头观察", "completed": False},
                    }
                )
                for index, shot in enumerate(paused["shots"]):
                    shot["analysisStatus"] = "analyzing" if index == 0 else "ok"
                paused_context, paused_page = open_state_page(paused)
                wait_text(paused_page, "#analysis-subline", "观察已中断", 15000)
                assert paused_page.locator(".rail-item.is-analyzing").count() == 0
                assert paused_page.locator('[data-action="cancel-analysis"]').is_hidden()
                paused_context.close()
                checks.append("paused：显示观察已中断，无永久转圈，取消按钮隐藏")

                # 失败信息中的 HTML 必须转义，不能注入脚本。
                failed = copy.deepcopy(real_status)
                failed.update(
                    {
                        "status": "failed",
                        "progress": 90,
                        "etaSeconds": None,
                        "stage": {"index": 4, "name": "逐镜头观察", "completed": False},
                        "error": {
                            "code": "internal_error",
                            "message": '<img src=x onerror="window.__pwn=1">',
                        },
                    }
                )
                failed["shots"][1]["analysisStatus"] = "failed"
                failed_context, failed_page = open_state_page(failed)
                wait_text(failed_page, "#analysis-subline", "<img src=x", 15000)
                assert failed_page.evaluate("window.__pwn") is None
                assert failed_page.locator("#analysis-subline img").count() == 0
                failed_page.locator(".rail-item").nth(1).click()
                wait_text(failed_page, '[data-role="failed-note"]', "历史报告", 15000)
                assert failed_page.locator('[data-action="retry-shot"]').count() == 0
                failed_context.close()
                checks.append("失败态：错误文案转义无 XSS，真实模式不展示假重试按钮")

                browser.close()
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

    print("PASS")
    for item in checks:
        print(f"  - {item}")
    print(f"截图目录：{artifacts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
