"""业务流程基类（端无关，跨端复用，全产品线一份）。

业务流程只编排页面实现的统一接口，禁止出现定位细节；
同一流程在不同端跑，靠注入该端的 Page 实现类完成。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from .page import Page

if TYPE_CHECKING:
    from .driver import Driver

P = TypeVar("P", bound=Page)


class Flow:
    """业务流程：持有驱动与页面缓存。子类实现业务步骤方法。"""

    def __init__(self, driver: Driver) -> None:
        self.driver = driver
        self._pages: dict[type[Page], Page] = {}

    def page(self, page_cls: type[P]) -> P:
        """获取某页面的本端实现（懒创建，按类缓存）。"""
        if page_cls not in self._pages:
            self._pages[page_cls] = page_cls(self.driver)
        return self._pages[page_cls]  # type: ignore[return-value]
