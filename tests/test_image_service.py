from __future__ import annotations

import io

import pytest
from PIL import Image

from app.services import image_service
from tests.helpers import make_image


def _decode(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


def test_process_valid_png():
    data = make_image()
    result = image_service.process_upload(data, "镜头.png", max_mb=20)

    assert result.extension == "png"
    assert result.mime_type == "image/png"
    assert (result.width, result.height) == (900, 1200)
    assert result.original_bytes == data
    assert len(result.sha256) == 64

    analysis = _decode(result.analysis_jpeg)
    assert analysis.mode == "RGB"
    assert max(analysis.size) <= image_service.ANALYSIS_MAX_EDGE
    thumb = _decode(result.thumb_jpeg)
    assert max(thumb.size) <= image_service.THUMB_MAX_EDGE


def test_rejects_unsupported_and_corrupt_files():
    with pytest.raises(image_service.ImageValidationError) as exc:
        image_service.process_upload(b"<svg>not an image</svg>", "fake.png", max_mb=20)
    assert exc.value.code == "unsupported_file"

    with pytest.raises(image_service.ImageValidationError):
        image_service.process_upload(b"", "empty.png", max_mb=20)


def test_rejects_over_limit_before_decode():
    with pytest.raises(image_service.ImageValidationError) as exc:
        image_service.process_upload(b"x" * (1024 * 1024 + 1), "big.png", max_mb=1)
    assert "1 MB" in exc.value.message


def test_alpha_flattened_on_white():
    data = make_image(mode="RGBA")
    result = image_service.process_upload(data, "alpha.png", max_mb=20)
    analysis = _decode(result.analysis_jpeg)
    assert analysis.mode == "RGB"


def test_exif_orientation_applied():
    image = Image.new("RGB", (400, 200), (200, 180, 160))
    exif = image.getexif()
    exif[274] = 6  # 顺时针 90°
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif.tobytes())

    result = image_service.process_upload(buffer.getvalue(), "rotated.jpg", max_mb=20)
    assert (result.width, result.height) == (200, 400)


def test_quality_warnings_for_dark_and_small():
    dark = make_image(size=(300, 300), base=(5, 5, 5), accent=(8, 8, 8))
    result = image_service.process_upload(dark, "dark.png", max_mb=20)
    assert any("偏暗" in warning for warning in result.warnings)
    assert any("分辨率" in warning for warning in result.warnings)
