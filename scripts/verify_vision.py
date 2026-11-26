"""最小化视觉服务连通性验证（手动执行，可能产生费用）。

用法（必须使用项目指定解释器）：
    set CHAR_CONS_ANALYSIS_MODEL=<控制台中的模型 ID>
    set CHAR_CONS_ANALYSIS_API_KEY=<Key>
    D:\\miniconda3\\miniconda3\\envs\\Agent\\python.exe scripts\\verify_vision.py
    ... --image 某张镜头.png      # 额外验证单镜头观察
    ... --mock                    # 不联网，验证结构化输出链路
"""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import Settings  # noqa: E402
from app.providers.factory import make_vision_provider  # noqa: E402
from app.providers.schemas import CharacterProfile  # noqa: E402
from app.services.profile_local import parse_profile_local  # noqa: E402
from app.services.script_parser import parse_script  # noqa: E402

SAMPLE = "阿岚，深棕长发低侧发髻，浅米色亚麻西装外套，黑色丝质衬衫，紫色口袋巾，圆形吊坠项链（蓝紫四瓣花）。"


def _dump(model) -> str:
    return json.dumps(model.model_dump(by_alias=True), ensure_ascii=False, indent=2)


async def run(args) -> int:
    settings = Settings.load()
    if args.mock:
        settings.analysis_provider = "mock"
        settings.analysis_model = "mock-vision"
    provider = make_vision_provider(settings)
    try:
        provider.ensure_configured()
    except Exception as exc:
        print(f"[配置错误] {exc}")
        print("请设置 CHAR_CONS_ANALYSIS_MODEL 与 Key（或配置 config.json / Windows 凭据管理器）。")
        return 2

    print(f"Provider: {getattr(provider, 'name', '?')} / Model: {getattr(provider, 'model_name', '?')}")
    result = await provider.parse_profile(SAMPLE)
    profile = result.value
    print(f"设定解析：explicit={profile.explicit_count}, requestId={result.request_id}")
    if profile.explicit_count == 0:
        print("（模型未返回显式要素，展示本地规则回退结果）")
        profile = parse_profile_local(SAMPLE)
    print(_dump(profile))

    if args.image:
        image_path = Path(args.image)
        if not image_path.is_file():
            print(f"[错误] 图片不存在：{image_path}")
            return 2
        script = parse_script("这些镜头为同一场戏的连续动作，无换装情节。", ["S1"])
        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        observation = await provider.observe_shot(
            image_path.read_bytes(),
            mime_type=mime_type,
            shot_code="S1",
            note="",
            profile=profile,
            script=script,
        )
        print(f"单镜头观察：requestId={observation.request_id}, usage={observation.usage}")
        print(_dump(observation.value))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="char_cons 视觉服务连通性验证")
    parser.add_argument("--image", help="可选：单张镜头图片路径")
    parser.add_argument("--mock", action="store_true", help="使用 Mock Provider，不联网")
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        raise SystemExit(130)


if __name__ == "__main__":
    main()
