"""YAML 配置加载与校验。错误信息必须能让人一眼改对配置。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..core.errors import ConfigError
from .model import AndroidApp, AppProfile, FrameworkConfig, MiniProgram, Settings


def load_config_file(path: str | Path) -> FrameworkConfig:
    p = Path(path)
    if not p.exists():
        raise ConfigError(
            f"配置文件不存在: {p}。请从 profiles/apps.example.yaml 复制一份并填入产品线信息。"
        )
    return load_config_str(p.read_text(encoding="utf-8"))


def load_config_str(text: str) -> FrameworkConfig:
    """从 YAML 文本加载（测试与工具用）。"""
    return load_config_dict(yaml.safe_load(text))


def load_config_dict(data: dict[str, Any]) -> FrameworkConfig:
    if not isinstance(data, dict):
        raise ConfigError("配置根节点必须是映射")
    settings = Settings(**_section(data, "defaults", {}))
    apps_data = data.get("apps")
    if not isinstance(apps_data, dict) or not apps_data:
        raise ConfigError("配置缺少 apps 段或为空")

    apps: dict[str, AppProfile] = {}
    for app_id, body in apps_data.items():
        apps[app_id] = _parse_app(app_id, body or {})
    return FrameworkConfig(settings=settings, apps=apps)


def _parse_app(app_id: str, body: dict[str, Any]) -> AppProfile:
    kind = body.get("kind", "app")
    android = AndroidApp(**_section(body, "android", {})) if "android" in body else None
    mp = MiniProgram(**_section(body, "miniprogram", {})) if "miniprogram" in body else None
    envs = body.get("envs") or {}
    if not isinstance(envs, dict):
        raise ConfigError(f"app {app_id}: envs 必须是映射")
    if kind == "app" and android is None:
        raise ConfigError(f"app {app_id}: kind=app 必须提供 android 段")
    if kind == "miniprogram" and mp is None:
        raise ConfigError(f"app {app_id}: kind=miniprogram 必须提供 miniprogram 段")
    return AppProfile(
        app_id=app_id,
        kind=kind,
        android=android,
        miniprogram=mp,
        envs=dict(envs),
    )


def _section(body: dict[str, Any], name: str, default: dict[str, Any]) -> dict[str, Any]:
    value = body.get(name, default)
    if not isinstance(value, dict):
        raise ConfigError(f"配置段 {name} 必须是映射，实际: {value!r}")
    return value
