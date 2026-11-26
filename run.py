"""本地启动脚本：读取配置后启动 Uvicorn，可选自动打开浏览器。

用法：
    D:\\miniconda3\\miniconda3\\envs\\Agent\\python.exe run.py
    D:\\miniconda3\\miniconda3\\envs\\Agent\\python.exe run.py --no-browser
"""

from __future__ import annotations

import argparse
import os
import threading
import time
import webbrowser

import uvicorn

from app.core.config import Settings
from app.core.logging import setup_logging


def _open_browser_later(url: str, delay: float = 2.0) -> None:
    def worker() -> None:
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:  # 浏览器打不开不影响服务
            pass

    threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 char_cons 本地服务")
    parser.add_argument("--port", type=int, help="覆盖配置中的端口")
    parser.add_argument("--host", default=None, help="覆盖监听地址（仅建议回环地址）")
    parser.add_argument("--reload", action="store_true", help="开发模式热重载")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    if args.port:
        os.environ["CHAR_CONS_PORT"] = str(args.port)
    if args.host:
        os.environ["CHAR_CONS_HOST"] = args.host

    settings = Settings.load()
    settings.ensure_dirs()
    setup_logging(settings.logs_dir)

    url = f"http://{settings.host}:{settings.port}/"
    print(f"char_cons 正在启动：{url}")
    if not args.no_browser:
        _open_browser_later(url)

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=args.reload,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
