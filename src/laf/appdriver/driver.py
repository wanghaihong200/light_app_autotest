"""混合 App 驱动（ADR-0001）：Appium + UiAutomator2。

核心职责：
1. 候选链定位时按候选类型自动切换上下文（css→WEBVIEW，其余→NATIVE）；
2. 把引擎类型封死在本模块内，对外只出 UniElement。
测试注入点：remote_factory 参数替换 appium.Remote，便于无设备单测。
"""

from __future__ import annotations

import json
from typing import Any, Callable

from ..core.driver import Driver, DriverContext, UniElement, find_via_chain
from ..core.errors import DriverError
from ..core.locator import Candidate, Locator

_drivers_loaded = False


def _load_appium():
    """延迟导入 appium，让无设备环境跑单测时不强制装它（装了也无妨）。"""
    global _drivers_loaded
    try:
        from appium import webdriver as appium_webdriver
        from appium.options.android import UiAutomator2Options
        from appium.webdriver.common.appiumby import AppiumBy
        from selenium.common.exceptions import NoSuchElementException
    except ImportError as exc:  # pragma: no cover
        raise DriverError(
            "appium-python-client 未安装：pip install appium-python-client"
        ) from exc
    return appium_webdriver, UiAutomator2Options, AppiumBy, NoSuchElementException


class AppElement(UniElement):
    def __init__(self, raw: Any) -> None:
        self.raw = raw

    def tap(self) -> None:
        self.raw.click()

    def input(self, text: str) -> None:
        self.raw.send_keys(text)

    def text(self) -> str:
        return self.raw.text

    def attribute(self, name: str) -> str | None:
        return self.raw.get_attribute(name)

    def is_visible(self) -> bool:
        return bool(self.raw.is_displayed())


def _default_remote(server_url: str, options: Any) -> Any:
    """appium-python-client 6.x：options 为 keyword-only。"""
    aw, _, _, _ = _load_appium()
    return aw.Remote(server_url, options=options)


class AppDriver(Driver):
    name = "app"

    def __init__(
        self,
        ctx: DriverContext,
        remote_factory: Callable[[str, Any], Any] | None = None,
    ) -> None:
        super().__init__(ctx)
        self._remote_factory = remote_factory or _default_remote
        self._wd: Any = None

    # -- 生命周期 ---------------------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        _, UiAutomator2Options, _, _ = _load_appium()
        opts = UiAutomator2Options()
        for k, v in self._capabilities().items():
            opts.set_capability(k, v)
        server: str = self.ctx.opt("appium_server")
        self._wd = self._remote_factory(server, opts)
        # noReset 语义下不保证前台化：显式激活被测包，
        # 避免残留在前台的其它 App 让用例在错误屏幕上跑（真机踩坑：浏览器占前台）
        package = self.ctx.opt("package")
        if package and not self.ctx.opt("apk"):
            try:
                self._wd.activate_app(package)
            except Exception as exc:  # noqa: BLE001 —— 激活失败留给 ready_marker 暴露
                pass
        self._started = True

    def stop(self) -> None:
        if self._wd is not None:
            try:
                self._wd.quit()
            finally:
                self._wd = None
                self._started = False

    def _capabilities(self) -> dict[str, Any]:
        caps: dict[str, Any] = {
            "platformName": "Android",
            "automationName": "UiAutomator2",
            "deviceName": getattr(self.ctx.device, "udid", "local"),
            "autoGrantPermissions": True,
            "newCommandTimeout": 300,
            # WebView 内核版本与内置 chromedriver 不匹配时自动下载对应版本
            "chromedriverAutodownload": True,
            # 国产 ROM（ColorOS/MIUI 等）常不给 shell 写 secure settings 的权限，
            # Appium 设 hidden_api_policy 被拒会导致会话创建失败——按官方建议忽略
            "ignoreHiddenApiPolicyError": True,
            # 共识约定"App 默认已登录"：不清数据保登录态；
            # ColorOS 亦禁止 shell pm clear（OplusClearDataProtectManager 拦截）
            "noReset": True,
        }
        if self.ctx.device is not None:
            caps["udid"] = self.ctx.device.udid
        apk = self.ctx.opt("apk")
        if apk:
            caps["app"] = apk
        else:
            caps["appPackage"] = self.ctx.opt("package")
            if self.ctx.opt("activity"):
                caps["appActivity"] = self.ctx.opt("activity")
        return caps

    # -- 元素操作 ---------------------------------------------------------

    def find(self, locator: Locator, timeout: float | None = None) -> UniElement:
        self._require_started()
        _, _, AppiumBy, NoSuchElem = _load_appium()
        timeout = self.ctx.opt("timeout") if timeout is None else timeout

        def find_one(cand: Candidate) -> UniElement | None:
            self._ensure_context(cand.is_web)
            by, value = _appium_by(AppiumBy, cand)
            try:
                return AppElement(self._wd.find_element(by, value))
            except NoSuchElem:
                return None

        return find_via_chain(find_one, locator, timeout)

    # -- 上下文切换 ---------------------------------------------------------

    def _ensure_context(self, want_web: bool) -> None:
        current = self._wd.current_context
        if want_web and current == "NATIVE_APP":
            self._switch_to_webview()
        elif not want_web and current != "NATIVE_APP":
            self._wd.switch_to.context("NATIVE_APP")

    def _switch_to_webview(self) -> None:
        package = self.ctx.opt("package") or ""
        contexts = self._wd.contexts
        for name in contexts:
            if package and name == f"WEBVIEW_{package}":
                self._wd.switch_to.context(name)
                return
        for name in contexts:
            if name.startswith("WEBVIEW_"):
                self._wd.switch_to.context(name)
                return
        raise DriverError(
            f"未发现 WEBVIEW 上下文（现有: {contexts}）。"
            "请确认 App 已开启 WebView 调试：WebView.setWebContentsDebuggingEnabled(true)"
        )

    @property
    def current_context(self) -> str:
        return self._wd.current_context

    # -- 会话操作 ---------------------------------------------------------

    def back(self) -> None:
        self._require_started()
        self._wd.back()

    def screenshot(self, path: str) -> str:
        self._require_started()
        self._wd.get_screenshot_as_file(path)
        return path

    def page_dump(self) -> str:
        self._require_started()
        if self._wd.current_context == "NATIVE_APP":
            return self._wd.page_source
        return str(self._wd.execute_script("return document.documentElement.outerHTML"))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self._require_started()
        self._wd.swipe(x1, y1, x2, y2, duration_ms)

    def screen_size(self) -> tuple[int, int]:
        self._require_started()
        size = self._wd.get_window_size()
        return int(size["width"]), int(size["height"])

    def press_enter(self) -> None:
        self._require_started()
        self._wd.execute_script("mobile: performEditorAction", {"action": "go"})

    def type_text(self, text: str) -> None:
        self._require_started()
        self._wd.execute_script("mobile: type", {"text": text})


def _appium_by(AppiumBy: Any, cand: Candidate) -> tuple[str, str]:
    if cand.strategy == "acc_id":
        return AppiumBy.ACCESSIBILITY_ID, cand.value
    if cand.strategy == "id":
        return AppiumBy.ID, cand.value
    if cand.strategy == "text":
        # UiAutomator 按文本定位：比 xpath 快且稳
        return AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{cand.value}")'
    if cand.strategy == "css":
        return AppiumBy.CSS_SELECTOR, cand.value
    if cand.strategy == "xpath":
        return AppiumBy.XPATH, cand.value
    raise DriverError(f"App 驱动不支持定位策略 {cand.strategy!r}（wx* 策略属小程序驱动）")


def json_safe(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
