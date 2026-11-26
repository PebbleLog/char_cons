"""最小化 Seedream 生成连通性检查（不打印 Key）。

用法：
    set CHAR_CONS_GENERATION_MODEL=<控制台模型 ID>
    set CHAR_CONS_GENERATION_API_KEY=<生成服务 Key>
    D:\\miniconda3\\miniconda3\\envs\\Agent\\python.exe scripts\\verify_generation.py
    ... --image 某参考镜头.png --prompt "中文提示词"
    ... --mock   # 仅验证本地闭环，不联网

注意：Seedream 5.5 单次只生成 1 张；4 张候选由业务层并行 4 次。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.providers.errors import ProviderError
from app.providers.factory import make_generation_provider


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default="阿岚，深棕长发低侧发髻，浅米色亚麻西装外套，圆形吊坠项链（蓝紫四瓣花），正面半身。")
    parser.add_argument("--image", type=Path, default=None, help="可选参考图")
    parser.add_argument("--size", default=None, help="可选尺寸档位，如 2K（以控制台为准）")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    settings = Settings.load()
    settings.ensure_dirs()
    if args.mock:
        settings.generation_provider = "mock"
    provider = make_generation_provider(settings)
    try:
        provider.ensure_configured()
        references: list[tuple[bytes, str]] = []
        if args.image:
            references.append((args.image.read_bytes(), "image/png"))
        generated = await provider.generate(
            prompt=args.prompt,
            references=references,
            size=args.size or settings.generation_size or None,
            seed=args.seed,
        )
    except ProviderError as exc:
        print(f"生成失败：{exc.code} · {exc.message}")
        return 1
    except OSError as exc:
        print(f"读取参考图失败：{exc}")
        return 1

    out = settings.home_dir / "verify_generation.png"
    out.write_bytes(generated.image_bytes)
    print("生成成功")
    print(f"provider={provider.name} model={generated.model}")
    print(f"request_id={generated.request_id or '—'} bytes={len(generated.image_bytes)}")
    print(f"本地文件={out}")
    print("模型 ID、参数与费用仍需以火山方舟控制台/实测为准【待实测】。")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
