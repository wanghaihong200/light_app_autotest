"""框架异常体系。所有异常继承 LafError，便于用例层统一兜底。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .locator import Locator


class LafError(Exception):
    """框架基础异常。"""


class DriverError(LafError):
    """驱动层错误（引擎不可用、上下文缺失等）。"""


class DriverNotStartedError(DriverError):
    """驱动未启动即被使用。"""


class ConfigError(LafError):
    """配置缺失或非法。"""


class LocatorError(LafError):
    """候选链全部落空。携带完整尝试轨迹，供失败现场包与快速修复。"""

    def __init__(self, locator: Locator, attempts: list[str]) -> None:
        self.locator = locator
        self.attempts = attempts
        trace = "\n  ".join(attempts) if attempts else "（无尝试记录）"
        super().__init__(f"定位失败: {locator}\n  尝试轨迹:\n  {trace}")
