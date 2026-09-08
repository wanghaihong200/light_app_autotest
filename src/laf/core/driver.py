"""Driver SPI（ADR-0003）：引擎无关的驱动接口。

约束：接口签名禁止泄漏任何底层引擎类型（Appium WebElement、automator Element…），
上层页面实现只面向 UniElement / Driver 编程。鸿蒙驱动一年后作为第三个实现插入。
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

from .errors import DriverNotStartedError, LafError, LocatorError
from .locator import Candidate, Locator


@dataclass
class DriverContext:
    """启动一个驱动所需的全部信息。由配置层构建，驱动自行解读 options。

    options 不设 schema——不同端的驱动各取所需（App 端要 package/activity，
    小程序端要 project_path/devtools_cli）。core 层不感知这些细节。
    """

    app_id: str
    env: str = "test"
    device: Any = None  # core.device.Device；小程序端可为 None
    options: dict[str, Any] = field(default_factory=dict)

    def opt(self, key: str, default: Any = None) -> Any:
        return self.options.get(key, default)


class UniElement(ABC):
    """引擎无关的元素接口。

    raw 属性是底层引擎元素的逃生舱，仅限证据采集/调试使用；
    页面实现层使用它属于违规（框架 lint 不检查此项，靠评审）。
    """

    raw: Any

    @abstractmethod
    def tap(self) -> None: ...

    @abstractmethod
    def input(self, text: str) -> None: ...

    @abstractmethod
    def text(self) -> str: ...

    @abstractmethod
    def attribute(self, name: str) -> str | None: ...

    @abstractmethod
    def is_visible(self) -> bool: ...


class Driver(ABC):
    """每端恰有一个实现的驱动接口。"""

    name: str = "abstract"

    def __init__(self, ctx: DriverContext) -> None:
        self.ctx = ctx
        self._started = False

    # -- 生命周期 ---------------------------------------------------------

    @abstractmethod
    def start(self) -> None:
        """建立与底层引擎的会话。幂等：已启动时为 no-op。"""

    @abstractmethod
    def stop(self) -> None:
        """结束会话并释放资源。幂等。"""

    def _require_started(self) -> None:
        if not self._started:
            raise DriverNotStartedError(
                f"驱动 {self.name} 尚未启动：请先调用 start()（或使用 driver fixture）"
            )

    # -- 元素操作 ----------------------------------------------------------

    @abstractmethod
    def find(self, locator: Locator, timeout: float = 10.0) -> UniElement:
        """按候选链轮询定位，返回首个命中的元素；超时抛 LocatorError。"""

    def exists(self, locator: Locator, timeout: float = 2.0) -> bool:
        """元素是否在超时内出现。默认实现复用 find。"""
        try:
            self.find(locator, timeout=timeout)
            return True
        except LocatorError:
            return False

    # -- 会话操作 ----------------------------------------------------------

    @abstractmethod
    def back(self) -> None:
        """返回上一页/上一屏。"""

    @abstractmethod
    def screenshot(self, path: str) -> str:
        """截图到指定路径，返回实际路径。"""

    @abstractmethod
    def page_dump(self) -> str:
        """当前页面结构快照（失败现场包用）：原生为控件树，WebView 为 HTML，
        小程序为 path+data JSON。"""

    @abstractmethod
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        """从 (x1,y1) 滑动到 (x2,y2)。"""

    @abstractmethod
    def screen_size(self) -> tuple[int, int]:
        """返回屏幕 (宽, 高)，单位 px。"""

    def press_enter(self) -> None:
        """触发输入法的确认/前往动作（地址栏导航等）。端不支持时抛错。"""
        raise LafError(f"驱动 {self.name} 不支持 press_enter")

    def type_text(self, text: str) -> None:
        """输入到当前焦点控件（tap 之后焦点控件常与被点控件不同）。"""
        raise LafError(f"驱动 {self.name} 不支持 type_text")


def find_via_chain(
    find_one: Callable[[Candidate], UniElement | None],
    locator: Locator,
    timeout: float,
    poll: float = 0.5,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> UniElement:
    """候选链轮询的通用实现，App/小程序/未来鸿蒙驱动共用。

    find_one 返回元素（命中）或 None（未命中）；抛异常视为该候选失败并记录。
    全部落空时抛 LocatorError，携带完整尝试轨迹。
    """
    deadline = clock() + timeout
    attempts: list[str] = []
    while True:
        for cand in locator.chain:
            try:
                el = find_one(cand)
            except Exception as exc:  # noqa: BLE001 —— 任何引擎异常都记录为该候选失败
                attempts.append(f"{cand}: {type(exc).__name__}: {exc}")
                continue
            if el is not None:
                return el
            attempts.append(f"{cand}: 未找到")
        if clock() >= deadline:
            break
        sleep(poll)
    raise LocatorError(locator, attempts)
