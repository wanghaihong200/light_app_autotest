"""驱动工厂：按 profile 的 kind 构造对应驱动。"""

from __future__ import annotations

from .core.driver import Driver, DriverContext
from .core.errors import ConfigError


def create_driver(ctx: DriverContext) -> Driver:
    """按 ctx.options['kind'] 构造驱动实例。不启动，启动交给调用方/fixture。"""
    kind = ctx.opt("kind")
    if kind == "app":
        from .appdriver.driver import AppDriver

        return AppDriver(ctx)
    if kind == "miniprogram":
        from .mpdriver.driver import MiniProgramDriver

        return MiniProgramDriver(ctx)
    raise ConfigError(f"未知驱动类型 {kind!r}（配置 kind 应为 app|miniprogram）")
