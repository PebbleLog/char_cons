"""测试素材生成工具。"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw


def make_image(
    size: tuple[int, int] = (900, 1200),
    base: tuple[int, int, int] = (205, 185, 160),
    accent: tuple[int, int, int] = (60, 70, 90),
    fmt: str = "PNG",
    mode: str = "RGB",
) -> bytes:
    image = Image.new("RGB", size, base)
    draw = ImageDraw.Draw(image)
    # 画一些结构，避免被判定为纯色/模糊
    draw.rectangle(
        [size[0] * 0.2, size[1] * 0.15, size[0] * 0.8, size[1] * 0.7],
        fill=accent,
    )
    draw.ellipse(
        [size[0] * 0.35, size[1] * 0.05, size[0] * 0.65, size[1] * 0.3],
        fill=(120, 90, 70),
    )
    draw.line([0, size[1] * 0.8, size[0], size[1] * 0.75], fill=(20, 20, 20), width=8)
    if mode != "RGB":
        image = image.convert(mode)
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def task_payload(**overrides):
    payload = {
        "name": "阿岚 · 测试任务",
        "characterName": "阿岚",
        "profileRaw": "阿岚，深棕长发低侧发髻，浅米色亚麻西装外套，黑色丝质衬衫，圆形吊坠项链（蓝紫四瓣花）。",
        "scriptRaw": "这些镜头为同一场戏的连续动作，无换装情节。",
        "defaultBatchSize": 4,
    }
    payload.update(overrides)
    return payload
