"""配置模型：YAML 三维 profile（App × 环境 × 设备）。

设备维度不进 YAML——设备是运行时事实（adb 枚举），YAML 只声明
App 与环境；设备由 DevicePool 分配或 --laf-udid 钉死。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.errors import ConfigError


@dataclass
class AndroidApp:
    package: str
    activity: str = ""
    apk: str = ""  # 提供则按 apk 安装启动，否则按 package+activity 启动已装应用


@dataclass
class MiniProgram:
    project_path: str  # 小程序工程目录（含 project.config.json）
    devtools_cli: str = ""  # 微信开发者工具 cli 路径；留空则要求 DevTools 已启动
    appid: str = ""
    #: 探索环境口子（真机调试 2.0 的 wsEndpoint），手工触发，不进 CI
    ws_endpoint: str = ""


@dataclass
class Settings:
    appium_server: str = "http://127.0.0.1:4723"
    timeout: float = 10.0
    poll_interval: float = 0.5
    artifacts_dir: str = "artifacts"
    node_bin: str = "node"


@dataclass
class AppProfile:
    app_id: str
    kind: str  # "app" | "miniprogram"
    android: AndroidApp | None = None
    miniprogram: MiniProgram | None = None
    envs: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class FrameworkConfig:
    settings: Settings
    apps: dict[str, AppProfile]

    def profile(self, app_id: str) -> AppProfile:
        try:
            return self.apps[app_id]
        except KeyError:
            raise ConfigError(
                f"未知的 app {app_id!r}，可用: {sorted(self.apps)}"
            ) from None

    def build_options(self, app_id: str, env: str) -> dict[str, Any]:
        """合成驱动启动 options：全局设置 + 端配置 + 环境变量。"""
        prof = self.profile(app_id)
        if env not in prof.envs:
            raise ConfigError(
                f"app {app_id!r} 没有环境 {env!r}，已声明: {sorted(prof.envs)}"
            )
        options: dict[str, Any] = {
            "kind": prof.kind,
            "timeout": self.settings.timeout,
            "poll_interval": self.settings.poll_interval,
            "env_vars": prof.envs[env],
        }
        if prof.kind == "app":
            if prof.android is None:
                raise ConfigError(f"app {app_id!r} 缺少 android 配置段")
            options.update(
                {
                    "package": prof.android.package,
                    "activity": prof.android.activity,
                    "apk": prof.android.apk,
                    "appium_server": self.settings.appium_server,
                }
            )
        elif prof.kind == "miniprogram":
            if prof.miniprogram is None:
                raise ConfigError(f"app {app_id!r} 缺少 miniprogram 配置段")
            mp = prof.miniprogram
            options.update(
                {
                    "project_path": mp.project_path,
                    "devtools_cli": mp.devtools_cli,
                    "appid": mp.appid,
                    "ws_endpoint": mp.ws_endpoint,
                    "node_bin": self.settings.node_bin,
                }
            )
        else:
            raise ConfigError(f"app {app_id!r} 的 kind 非法: {prof.kind!r}（应为 app|miniprogram）")
        return options
