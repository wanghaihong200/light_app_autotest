"""AppDriver 上下文切换与候选链轨迹（无设备，注入桩实现）。"""

import pytest
from selenium.common.exceptions import NoSuchElementException

from laf.appdriver.driver import AppDriver, _load_appium
from laf.core.driver import DriverContext
from laf.core.errors import LocatorError
from laf.core.locator import Locator

_, _, AppiumBy, _ = _load_appium()


class StubEl:
    def __init__(self, name: str) -> None:
        self.name = name
        self.typed: str | None = None

    def click(self) -> None: ...
    def send_keys(self, t: str) -> None:
        self.typed = t

    @property
    def text(self) -> str:
        return self.name

    def get_attribute(self, name: str) -> str | None:
        return "v"

    def is_displayed(self) -> bool:
        return True


class StubWD:
    def __init__(self, elements: dict[tuple[str, str], StubEl]) -> None:
        self.contexts = ["NATIVE_APP", "WEBVIEW_com.example.mall"]
        self._ctx = "NATIVE_APP"
        self.elements = elements
        self.finds: list[tuple[str, str, str]] = []
        self.swipes: list[tuple] = []
        self.switch_to = self

    def context(self, name: str) -> None:
        self._ctx = name

    @property
    def current_context(self) -> str:
        return self._ctx

    def find_element(self, by: str, value: str) -> StubEl:
        self.finds.append((self._ctx, by, value))
        el = self.elements.get((by, value))
        if el is None:
            raise NoSuchElementException(value)
        return el

    def get_window_size(self) -> dict[str, int]:
        return {"width": 1080, "height": 2400}

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> None:
        self.swipes.append((x1, y1, x2, y2, duration))
        # 第 2 次滑动后滚动到位：把目标元素放进控件树
        if len(self.swipes) >= 2:
            self.elements[(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("关于本机")')] = StubEl("about")

    def quit(self) -> None: ...


def make_driver(elements: dict[tuple[str, str], StubEl]) -> tuple[AppDriver, StubWD]:
    stub = StubWD(elements)
    ctx = DriverContext(
        app_id="mall",
        options={"kind": "app", "package": "com.example.mall",
                 "timeout": 1, "poll_interval": 0.1,
                 "appium_server": "http://127.0.0.1:4723"},
    )
    drv = AppDriver(ctx, remote_factory=lambda opts, server: stub)
    drv.start()
    return drv, stub


def test_css_candidate_switches_to_webview():
    el = StubEl("pay-btn")
    drv, stub = make_driver({(AppiumBy.CSS_SELECTOR, "#pay"): el})
    found = drv.find(Locator(css="#pay", desc="支付按钮"), timeout=2)
    assert found.text() == "pay-btn"
    assert stub.finds[0][0].startswith("WEBVIEW_")  # 定位前已切上下文


def test_native_candidate_stays_native():
    el = StubEl("btn")
    drv, stub = make_driver({(AppiumBy.ID, "com.example.mall:id/btn"): el})
    drv.find(Locator(id="com.example.mall:id/btn"), timeout=2)
    assert stub.finds[0][0] == "NATIVE_APP"


def test_all_candidates_miss_raises_locator_error_with_trace():
    drv, _ = make_driver({})
    with pytest.raises(LocatorError) as exc_info:
        drv.find(Locator(id="x:id/a", text="提交", css=".s"), timeout=0.6)
    trace = "\n".join(exc_info.value.attempts)
    # 每个候选至少尝试一轮，且轨迹包含完整候选描述
    for cand in ("id=x:id/a", "text=提交", "css=.s"):
        assert cand in trace


def test_exists_false_on_miss():
    drv, _ = make_driver({})
    assert drv.exists(Locator(id="x:id/none"), timeout=0.3) is False


def test_page_scroll_to_finds_after_swipes():
    from laf.core.page import Page

    drv, stub = make_driver({})

    class LongListPage(Page):
        LOCATORS = {"about": Locator(text="关于本机", desc="关于本机")}

    page = LongListPage(drv, timeout=1.0)
    el = page.scroll_to("about", max_swipes=4)
    assert el.text() == "about"
    assert len(stub.swipes) >= 2  # 滑动后命中
