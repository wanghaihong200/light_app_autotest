"""Page.wait_ready 行为测试：超时必须响亮失败。"""

import pytest

from laf.core.errors import LafError, LocatorError
from laf.core.locator import Locator
from laf.core.page import Page


class MissingDriver:
    def find(self, locator, timeout=10.0):
        raise LocatorError(locator, [f"{locator}: 未找到"])


def test_wait_ready_raises_when_marker_missing():
    class Home(Page):
        ready_marker = Locator(text="ready", desc="就绪标志")

    with pytest.raises(LafError, match="未就绪"):
        Home(MissingDriver()).wait_ready(timeout=1)


def test_wait_ready_noop_without_marker():
    class Home(Page):
        LOCATORS: dict = {}

    Home(MissingDriver()).wait_ready()  # 无 marker：no-op，不应抛错
