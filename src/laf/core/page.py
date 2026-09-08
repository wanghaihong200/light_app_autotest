"""页面实现基类（每端一个子类）。

约定（ADR-0004）：定位器只允许声明在 LOCATORS 类属性中，
用例与业务流程只能通过 page.loc(name) / page.on(name) 访问。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from .errors import LafError
from .locator import Locator

if TYPE_CHECKING:
    from .driver import Driver, UniElement


class Page:
    """某端一个页面的实现。子类声明 LOCATORS 与（可选的）ready_marker。"""

    LOCATORS: ClassVar[dict[str, Locator]] = {}
    #: 页面就绪标志：wait_ready 轮询它，业务流程进入页面前先 wait_ready
    ready_marker: Locator | None = None

    def __init__(self, driver: Driver, timeout: float = 10.0) -> None:
        self.driver = driver
        self.timeout = timeout

    def loc(self, name: str) -> Locator:
        try:
            return self.LOCATORS[name]
        except KeyError:
            raise LafError(
                f"{type(self).__name__} 中没有定位器 {name!r}；"
                f"已声明: {sorted(self.LOCATORS)}。定位器必须声明在 LOCATORS 中。"
            ) from None

    def on(self, name: str, timeout: float | None = None) -> UniElement:
        """定位并返回元素（走候选链轮询）。"""
        return self.driver.find(self.loc(name), timeout=timeout or self.timeout)

    def has(self, name: str, timeout: float = 2.0) -> bool:
        """元素是否出现。"""
        return self.driver.exists(self.loc(name), timeout=timeout)

    def wait_ready(self, timeout: float | None = None) -> None:
        """等待页面就绪；超时抛 LafError（禁止静默通过——那是错误屏幕上跑用例的根源）。

        未声明 ready_marker 时为 no-op。
        """
        if self.ready_marker is None:
            return
        from .errors import LafError, LocatorError

        try:
            self.driver.find(self.ready_marker, timeout=timeout or self.timeout)
        except LocatorError as exc:
            raise LafError(
                f"页面 {type(self).__name__} 未就绪（ready_marker 超时未出现）。"
                "常见原因：被测 App 未到前台/落在了错误页面。原始定位轨迹：\n"
                f"{exc}"
            ) from exc

    def scroll_to(
        self,
        name: str,
        max_swipes: int = 6,
        timeout: float = 1.0,
    ) -> UniElement:
        """向上滑动翻页查找目标元素（长列表刚需）。

        每次滑动后用短超时 find 探测，命中即返回；滑满 max_swipes 仍
        未命中则抛最后一次的 LocatorError（含完整尝试轨迹）。
        """
        from .errors import LocatorError

        w, h = self.driver.screen_size()
        last_error: LocatorError | None = None
        for _ in range(max_swipes):
            try:
                return self.driver.find(self.loc(name), timeout=timeout)
            except LocatorError as exc:
                last_error = exc
            self.driver.swipe(int(w * 0.5), int(h * 0.75), int(w * 0.5), int(h * 0.35), 400)
        assert last_error is not None
        raise last_error
