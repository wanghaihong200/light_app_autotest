"""小程序驱动单元测试（注入假 sidecar，不需要 Node/DevTools）。"""

import pytest

from laf.core.driver import DriverContext
from laf.core.errors import LocatorError
from laf.core.locator import Locator
from laf.mpdriver.driver import MiniProgramDriver


class FakeTransport:
    def __init__(self, results: dict) -> None:
        self.results = results
        self.calls: list[tuple[str, dict]] = []

    def call(self, method: str, **params):
        self.calls.append((method, params))
        result = self.results.get(method)
        if isinstance(result, Exception):
            raise result
        return result  # 未声明的方法默认返回 None（未命中）

    def close(self) -> None: ...


class FakeSidecar:
    def __init__(self, transport: FakeTransport) -> None:
        self._transport = transport
        self.stopped = False

    def start(self) -> FakeTransport:
        return self._transport

    def stop(self) -> None:
        self.stopped = True


def make_driver(results: dict) -> tuple[MiniProgramDriver, FakeTransport]:
    transport = FakeTransport(results)
    ctx = DriverContext(
        app_id="mall_mp",
        options={"kind": "miniprogram", "project_path": "/tmp/mp",
                 "timeout": 1, "poll_interval": 0.1},
    )
    drv = MiniProgramDriver(ctx, sidecar=FakeSidecar(transport))
    drv.start()
    return drv, transport


def test_start_launches_with_project_path():
    drv, tp = make_driver({"launch": True})
    assert tp.calls[0][0] == "launch"
    assert tp.calls[0][1]["project_path"] == "/tmp/mp"


def test_wx_class_candidate_maps_to_selector():
    drv, tp = make_driver({"launch": True, "query": "h1", "element_text": "购物车"})
    el = drv.find(Locator(wx="cart-btn"))
    assert el.text() == "购物车"
    assert ("query", {"selector": ".cart-btn"}) in tp.calls


def test_text_candidate_uses_find_by_text_with_hint():
    drv, tp = make_driver({"launch": True, "find_by_text": "h2",
                           "element_text": "加入购物车"})
    el = drv.find(Locator(wx_tag="view", text="加入购物车"))
    assert el.text() == "加入购物车"
    # hint 取链中第一个结构候选，而非默认 view
    assert ("find_by_text", {"selector": "view", "text": "加入购物车"}) in tp.calls


def test_all_miss_raises_locator_error():
    drv, _ = make_driver({"launch": True, "query": None, "find_by_text": None})
    with pytest.raises(LocatorError):
        drv.find(Locator(wx_id="go", text="结算"), timeout=0.6)


def test_element_ops_proxy_to_sidecar():
    drv, tp = make_driver({"launch": True, "query": "h1", "element_size":
                           {"width": 10, "height": 0}})
    el = drv.find(Locator(wx="btn"))
    el.tap()
    el.input("文本")
    assert ("element_tap", {"handle": "h1"}) in tp.calls
    assert ("element_input", {"handle": "h1", "value": "文本"}) in tp.calls
    assert el.is_visible() is False  # 高度为 0 视为不可见


def test_page_dump_contains_path_and_data():
    drv, _ = make_driver({"launch": True, "current_page": {"path": "pages/index/index"},
                          "page_data": {"cartCount": 2}})
    dump = drv.page_dump()
    assert "pages/index/index" in dump and "cartCount" in dump


def test_stop_terminates_sidecar():
    drv, _ = make_driver({"launch": True, "close": True})
    drv.stop()
    assert drv._sidecar.stopped  # noqa: SLF001 —— 单测断言内部状态
