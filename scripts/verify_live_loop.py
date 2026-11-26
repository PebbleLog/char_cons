"""真实模型闭环实测（手动、会产生费用）：分析 → 报告 → 生成 → 预检 → 采用 → 复检。

默认使用 frontend/assets 中的定稿示例镜头，不发送任何本地私有素材。
运行前配置：
    set CHAR_CONS_ANALYSIS_MODEL=<视觉模型 ID>
    set CHAR_CONS_ANALYSIS_API_KEY=<分析 Key>
    set CHAR_CONS_GENERATION_MODEL=<Seedream 模型 ID>
    set CHAR_CONS_GENERATION_API_KEY=<生成 Key>

执行：
    D:\\miniconda3\\miniconda3\\envs\\Agent\\python.exe scripts\\verify_live_loop.py --yes --candidates 1

脚本使用临时数据目录，不写入真实历史；不会打印 Key。真实时延/费用、并发稳定性
与角色一致性结果请记录到 README 的「测试与验证」章节。
"""

from __future__ import annotations

import argparse
import io
import mimetypes
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.providers.factory import (  # noqa: E402
    make_generation_provider,
    make_vision_provider,
)

PROFILE = (
    "阿岚，深棕长发低侧发髻，浅米色亚麻西装外套，黑色丝质衬衫，紫色口袋巾，"
    "圆形吊坠项链（蓝紫四瓣花）。"
)
SCRIPT = "这些镜头为同一场戏的连续动作，无换装情节。"


def _default_images() -> list[Path]:
    candidates = [
        ROOT / "frontend" / "assets" / "shot-1.jpg",
        ROOT / "frontend" / "assets" / "shot-2.jpg",
        ROOT / "frontend" / "assets" / "shot-3.jpg",
    ]
    existing = [path for path in candidates if path.is_file()]
    if existing:
        return existing
    # 交付包缺失示例素材时使用合成测试图，仅用于验证接口链路。
    paths = []
    for index in range(1, 4):
        image = Image.new("RGB", (900, 1200), (200 - index * 10, 185, 165))
        draw = ImageDraw.Draw(image)
        draw.rectangle([180, 180, 720, 840], fill=(60, 70, 90))
        draw.ellipse([315, 60, 585, 360], fill=(120, 90, 70))
        path = Path(tempfile.gettempdir()) / f"char_cons_live_shot_{index}.png"
        image.save(path)
        paths.append(path)
    return paths


def _wait(client: TestClient, path: str, terminal: set[str], timeout: float, key: str = "status"):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = client.get(path).json()
        if last.get(key) in terminal:
            return last
        time.sleep(1.0)
    raise TimeoutError(f"等待超时：{path}，最后状态 {last}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="确认会产生真实模型费用")
    parser.add_argument("--candidates", type=int, default=1, choices=range(1, 5))
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--no-adopt", action="store_true")
    parser.add_argument("--images", nargs="*", type=Path)
    args = parser.parse_args()
    if not args.yes:
        print("未执行：真实模型调用会产生费用。确认后请追加 --yes。")
        return 2

    images = args.images or _default_images()
    with tempfile.TemporaryDirectory(prefix="char_cons_live_") as home:
        settings = Settings.load(home_dir=Path(home))
        settings.ensure_dirs()
        if settings.analysis_provider != "doubao" or settings.generation_provider != "doubao":
            print("未执行：真实闭环要求分析与生成 provider 均为 doubao（不能使用 mock）。")
            return 2
        try:
            make_vision_provider(settings).ensure_configured()
            make_generation_provider(settings).ensure_configured()
        except Exception as exc:
            print(f"[配置错误] {exc}")
            print("请先配置分析/生成模型 ID 与各自独立的 Key。")
            return 2

        print(
            f"真实闭环开始：analysis={settings.analysis_model} "
            f"generation={settings.generation_model} candidates={args.candidates}"
        )
        app = create_app(settings, configure_logs=False)
        with TestClient(app) as client:
            csrf = client.get("/api/session").json()["csrfToken"]
            headers = {"X-CSRF-Token": csrf}
            task = client.post(
                "/api/tasks",
                json={
                    "name": "真实模型闭环验证",
                    "characterName": "阿岚",
                    "profileRaw": PROFILE,
                    "scriptRaw": SCRIPT,
                    "defaultBatchSize": args.candidates,
                },
                headers=headers,
            )
            task.raise_for_status()
            task_id = task.json()["id"]
            files = [
                (
                    "files",
                    (
                        path.name,
                        path.read_bytes(),
                        mimetypes.guess_type(path.name)[0] or "image/jpeg",
                    ),
                )
                for path in images
            ]
            upload = client.post(f"/api/tasks/{task_id}/shots", files=files, headers=headers)
            upload.raise_for_status()
            print(f"已上传 {len(upload.json().get('shots', []))} 张镜头，开始真实分析…")

            started = time.perf_counter()
            analyzed = client.post(f"/api/tasks/{task_id}/analyze", headers=headers)
            analyzed.raise_for_status()
            status = _wait(
                client,
                f"/api/tasks/{task_id}/analysis",
                {"completed", "partial", "failed"},
                args.timeout,
            )
            analysis_seconds = time.perf_counter() - started
            print(f"分析完成：{status['status']} · {analysis_seconds:.1f}s")
            if status["status"] == "failed":
                print("分析失败，停止。")
                return 1
            report = client.get(f"/api/tasks/{task_id}/report").json()
            print(
                f"统计：一致 {report['stats']['consistent']} / "
                f"问题 {report['stats']['confirmedIssues']} / "
                f"无法判断 {report['stats']['unknown']} / "
                f"疑似 {report['stats']['suspectedIssues']}"
            )
            issues = report["issues"]
            if not issues:
                print("本次没有确定问题，无需生成。")
                return 0
            issue = issues[0]
            print(f"使用问题 {issue['id']} · {issue['shotCode']} · {issue['attributeName']} 验证生成闭环")

            started = time.perf_counter()
            generated = client.post(
                f"/api/tasks/{task_id}/issues/{issue['id']}/generate",
                json={"candidateCount": args.candidates},
                headers=headers,
            )
            generated.raise_for_status()
            generation_id = generated.json()["id"]
            generation = _wait(
                client,
                f"/api/tasks/{task_id}/generations/{generation_id}",
                {"succeeded", "partial", "failed"},
                args.timeout,
            )["generation"]
            generation_seconds = time.perf_counter() - started
            print(
                f"生成完成：{generation['status']} · {generation_seconds:.1f}s · "
                f"候选 {len(generation['candidates'])} · 预检 {generation['precheckStatus']}"
            )
            for candidate in generation["candidates"]:
                precheck = candidate.get("precheck") or {}
                print(
                    f"  {candidate['candidateCode']} · {candidate['state']} · "
                    f"{precheck.get('summary') or ''}"
                )
            if not generation["candidates"] or args.no_adopt:
                print("未采用候选；流程结束。")
                return 0
            candidate = generation["candidates"][0]
            started = time.perf_counter()
            adopted = client.post(
                f"/api/tasks/{task_id}/generations/{generation_id}/adopt",
                json={"candidateId": candidate["id"]},
                headers=headers,
            )
            adopted.raise_for_status()
            adoption = adopted.json().get("adoption")
            recheck_seconds = time.perf_counter() - started
            print(
                f"采用 {candidate['candidateCode']} · 复检 {adoption.get('recheckStatus')} · "
                f"{recheck_seconds:.1f}s"
            )
            after = client.get(f"/api/tasks/{task_id}/report").json()
            print(
                f"复检后统计：一致 {after['stats']['consistent']} / "
                f"问题 {after['stats']['confirmedIssues']} / "
                f"无法判断 {after['stats']['unknown']}"
            )
            print(
                f"时延记录：analysis={analysis_seconds:.1f}s "
                f"generation={generation_seconds:.1f}s recheck={recheck_seconds:.1f}s"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
