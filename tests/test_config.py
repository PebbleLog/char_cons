from __future__ import annotations

import json

from app.core.config import Settings


def test_ensure_dirs_creates_layout(tmp_path):
    settings = Settings(home_dir=tmp_path / "home")
    settings.ensure_dirs()
    for path in (
        settings.home_dir,
        settings.data_dir,
        settings.uploads_dir,
        settings.generated_dir,
        settings.exports_dir,
        settings.logs_dir,
    ):
        assert path.is_dir()
    assert settings.db_path == settings.home_dir / "char_cons.db"


def test_load_reads_whitelisted_config(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.json").write_text(
        json.dumps({"port": 8899, "upload_max_mb": 30, "unknown_key": 1}),
        encoding="utf-8",
    )

    settings = Settings.load(home_dir=home)

    assert settings.port == 8899
    assert settings.upload_max_mb == 30
    assert not hasattr(settings, "unknown_key")


def test_load_ignores_invalid_values(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.json").write_text(
        json.dumps({"port": "not-a-port", "default_batch_size": 99}),
        encoding="utf-8",
    )

    settings = Settings.load(home_dir=home)

    # 类型错误与越界值都应回落到默认值，避免一处手误导致无法启动
    assert settings.port == 8765
    assert settings.default_batch_size == 4
    settings.validate()


def test_env_overrides_port(tmp_path, monkeypatch):
    monkeypatch.setenv("CHAR_CONS_HOME", str(tmp_path / "envhome"))
    monkeypatch.setenv("CHAR_CONS_PORT", "8900")

    settings = Settings.load()

    assert settings.port == 8900
    assert settings.home_dir == (tmp_path / "envhome").resolve()


def test_public_config_contains_no_paths(tmp_path):
    settings = Settings(home_dir=tmp_path / "home")
    config = settings.public_config()

    assert "home_dir" not in config
    assert "frontend_dir" not in config
    assert config["port"] == 8765


def test_generation_config_from_env_and_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CHAR_CONS_HOME", str(tmp_path / "genhome"))
    monkeypatch.setenv("CHAR_CONS_GENERATION_PROVIDER", "mock")
    monkeypatch.setenv("CHAR_CONS_GENERATION_MODEL", "seedream-test")
    monkeypatch.setenv("CHAR_CONS_GENERATION_SIZE", "2K")
    settings = Settings.load()
    assert settings.generation_provider == "mock"
    assert settings.generation_model == "seedream-test"
    assert settings.generation_size == "2K"
    assert settings.generation_base_url.startswith("https://")
    assert settings.public_config()["generation_model"] == "seedream-test"


def test_generation_config_rejects_invalid_provider(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.json").write_text(
        json.dumps({"generation_provider": "other"}), encoding="utf-8"
    )
    try:
        Settings.load(home_dir=home)
    except ValueError as exc:
        assert "generation_provider" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("非法生成提供方应被拒绝")
