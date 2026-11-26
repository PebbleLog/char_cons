"""Windows 本地启动验证：启动 run.py，检查健康、静态页面与七页路由。

用法：
    D:\\miniconda3\\miniconda3\\envs\\Agent\\python.exe scripts\\verify_startup.py
    ... --port 8877

脚本使用临时数据目录，不触碰 %APPDATA% 下的真实数据；结束会终止子进程。
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SCREENS = (
    "screen-home",
    "screen-create",
    "screen-analysis",
    "screen-results",
    "screen-optimizer",
    "screen-history",
    "screen-settings",
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    port = args.port or _free_port()
    base = f"http://127.0.0.1:{port}"

    with tempfile.TemporaryDirectory(prefix="char_cons_startup_") as home:
        env = {
            **os.environ,
            "CHAR_CONS_HOME": home,
            "CHAR_CONS_PORT": str(port),
            "CHAR_CONS_ANALYSIS_PROVIDER": "mock",
            "CHAR_CONS_ANALYSIS_MODEL": "mock-vision",
            "CHAR_CONS_GENERATION_PROVIDER": "mock",
            "CHAR_CONS_GENERATION_MODEL": "mock-seedream",
        }
        creationflags = (
            subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        )
        process = subprocess.Popen(
            [sys.executable, "run.py", "--no-browser", "--port", str(port)],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
        try:
            deadline = time.time() + args.timeout
            health = None
            while time.time() < deadline:
                if process.poll() is not None:
                    output = process.stdout.read() if process.stdout else ""
                    print("启动失败，进程提前退出：")
                    print(output)
                    return 1
                try:
                    response = httpx.get(f"{base}/api/health", timeout=2.0)
                    if response.status_code == 200:
                        health = response.json()
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.3)
            if health is None:
                print("启动超时：未在限定时间内通过健康检查。")
                return 1

            page = httpx.get(f"{base}/", timeout=5.0)
            page.raise_for_status()
            missing = [screen for screen in SCREENS if f'id="{screen}"' not in page.text]
            if missing:
                print(f"页面缺少视图：{', '.join(missing)}")
                return 1
            session = httpx.get(f"{base}/api/session", timeout=5.0).json()
            settings = httpx.get(f"{base}/api/settings", timeout=5.0)
            settings.raise_for_status()
            tasks = httpx.get(f"{base}/api/tasks", timeout=5.0)
            tasks.raise_for_status()

            print("启动验证通过")
            print(f"URL={base}")
            print(
                f"health={health['status']} db={health['checks']['database']} "
                f"storage={health['checks']['storage']} mode={session['mode']}"
            )
            print(f"screens={len(SCREENS)} settings={settings.status_code} tasks={tasks.status_code}")
            return 0
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
