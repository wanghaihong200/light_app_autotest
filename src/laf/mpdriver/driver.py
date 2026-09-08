"""小程序驱动（ADR-0002/0003）：sidecar 协议的 Python 侧实现。

候选策略映射：wx_id→#id、wx→.class、wx_tag→标签、text→sidecar findByText。
测试注入点：_transport 可替换为假实现，无需 Node/DevTools 即可单测。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..core.driver import Driver, DriverContext, UniElement, find_via_chain
from ..core.locator import Candidate, Locator
from .transport import SidecarTransport, SubprocessSidecar


class MPElement(UniElement):
    def __init__(self, driver: MiniProgramDriver, handle: str) -> None:
        self._driver = driver
        self.raw = handle  # 逃生舱：sidecar 元素句柄

    def tap(self) -> None:
        self._driver._call("element_tap", handle=self.raw)

    def input(self, text: str) -> None:
        self._driver._call("element_input", handle=self.raw, value=text)

    def text(self) -> str:
        return str(self._driver._call("element_text", handle=self.raw) or "")

    def attribute(self, name: str) -> str | None:
        result = self._driver._call("element_attribute", handle=self.raw, name=name)
        return None if result is None else str(result)

    def is_visible(self) -> bool:
        size = self._driver._call("element_size", handle=self.raw) or {}
        return bool(size.get("width", 0) > 0 and size.get("height", 0) > 0)


class MiniProgramDriver(Driver):
    name = "miniprogram"

    def __init__(
        self,
        ctx: DriverContext,
        sidecar: SubprocessSidecar | None = None,
    ) -> None:
        super().__init__(ctx)
        self._sidecar = sidecar
        self._launched = False

    # -- 测试注入 ---------------------------------------------------------

    def _transport(self) -> SidecarTransport:
        if self._sidecar is not None:
            return self._sidecar.start()
        raise RuntimeError("sidecar 未初始化：请用 start() 或注入 SubprocessSidecar")

    def _call(self, method: str, **params: Any) -> Any:
        return self._transport().call(method, **params)

    # -- 生命周期 ---------------------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        if self._sidecar is None:
            self._sidecar = SubprocessSidecar(node_bin=self.ctx.opt("node_bin", "node"))
        transport = self._sidecar.start()
        ws_endpoint = self.ctx.opt("ws_endpoint")
        if ws_endpoint:  # 探索环境口子：真机调试 2.0，手工触发，不进 CI
            transport.call("connect", ws_endpoint=ws_endpoint)
        else:
            transport.call(
                "launch",
                project_path=self.ctx.opt("project_path"),
                devtools_cli=self.ctx.opt("devtools_cli") or None,
                appid=self.ctx.opt("appid") or None,
            )
        self._launched = True
        self._started = True

    def stop(self) -> None:
        if self._sidecar is not None:
            try:
                if self._launched:
                    self._sidecar.transport and self._sidecar.transport.call("close")
            except Exception:  # noqa: BLE001 —— 关闭失败不掩盖用例结果
                pass
            self._sidecar.stop()
            self._launched = False
        self._started = False

    # -- 元素操作 ---------------------------------------------------------

    def find(self, locator: Locator, timeout: float | None = None) -> UniElement:
        self._require_started()
        timeout = self.ctx.opt("timeout") if timeout is None else timeout
        hint = _selector_hint(locator)

        def find_one(cand: Candidate) -> UniElement | None:
            handle = self._find_handle(cand, hint)
            return None if handle is None else MPElement(self, str(handle))

        return find_via_chain(find_one, locator, timeout)

    def _find_handle(self, cand: Candidate, hint: str) -> str | None:
        if cand.strategy == "text":
            return self._call("find_by_text", selector=hint, text=cand.value)
        return self._call("query", selector=_selector_of(cand))

    # -- 会话操作 ---------------------------------------------------------

    def back(self) -> None:
        self._require_started()
        self._call("navigate", method="navigateBack")

    def navigate(self, method: str, path: str = "") -> None:
        """reLaunch / switchTab / navigateTo / navigateTo；供页面路由使用。"""
        self._require_started()
        self._call("navigate", method=method, url=path)

    def screenshot(self, path: str) -> str:
        self._require_started()
        self._call("screenshot", path=str(Path(path).resolve()))
        return path

    def page_dump(self) -> str:
        self._require_started()
        info = {
            "current_page": self._call("current_page"),
            "page_data": self._call("page_data"),
        }
        return json.dumps(info, ensure_ascii=False, indent=2, default=str)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self._require_started()
        self._call("swipe", x1=x1, y1=y1, x2=x2, y2=y2, duration=duration_ms)

    def screen_size(self) -> tuple[int, int]:
        self._require_started()
        info = self._call("system_info") or {}
        return int(info["windowWidth"]), int(info["windowHeight"])

    # -- 小程序特有能力（automator 逻辑层红利） ------------------------------

    def call_wx_method(self, method: str, *args: Any) -> Any:
        return self._call("call_wx_method", method=method, args=list(args))

    def page_data(self, path: str | None = None) -> Any:
        return self._call("page_data", path=path)


def _selector_of(cand: Candidate) -> str:
    if cand.strategy == "wx_id":
        return f"#{cand.value}"
    if cand.strategy == "wx":
        return f".{cand.value}"
    if cand.strategy == "wx_tag":
        return cand.value
    raise ValueError(f"小程序驱动不支持定位策略 {cand.strategy!r}")


def _selector_hint(locator: Locator) -> str:
    """findByText 的容器选择器：取链中第一个 wx 结构候选，否则 view。"""
    for cand in locator.chain:
        if cand.strategy in ("wx_id", "wx", "wx_tag"):
            return _selector_of(cand)
    return "view"
