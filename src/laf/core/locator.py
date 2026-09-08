"""定位器与候选链（ADR-0004 第一等公民）。

页面实现层只允许在 Page.LOCATORS 中声明 Locator；
候选链按声明时的策略自动排序：id → text → wx_id → wx → wx_tag → css → xpath。
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import LafError

#: 候选链的固定优先级：越靠前越稳定
STRATEGY_PRIORITY: tuple[str, ...] = (
    "acc_id",   # accessibility id（Android content-desc）；图标按钮的唯一稳定锚点
    "id",       # Android resource-id（原生）
    "text",     # 控件文本（原生）；小程序中经 findByText 处理
    "wx_id",    # 小程序组件 id（WXML id 属性），选择器形如 #xxx
    "wx",       # 小程序 class（不含点号），选择器形如 .xxx
    "wx_tag",   # 小程序标签名，如 view / text
    "css",      # WebView 页 CSS 选择器（触发 webview 上下文切换）
    "xpath",    # 兜底，最脆弱，永远排最后
)


@dataclass(frozen=True)
class Candidate:
    """单个候选定位。strategy 取值见 STRATEGY_PRIORITY。"""

    strategy: str
    value: str

    @property
    def is_web(self) -> bool:
        """该候选是否需要 WebView 上下文。"""
        return self.strategy == "css"

    def __str__(self) -> str:
        return f"{self.strategy}={self.value}"


class Locator:
    """一个控件的定位描述：按固定优先级组成候选链。

    用法（仅限 Page.LOCATORS 内）::

        LOCATORS = {
            "submit_btn": Locator(id="com.x:id/submit", text="提交",
                                  css="#submit", desc="提交按钮"),
        }
    """

    def __init__(
        self,
        *,
        acc_id: str | None = None,
        id: str | None = None,
        text: str | None = None,
        wx_id: str | None = None,
        wx: str | None = None,
        wx_tag: str | None = None,
        css: str | None = None,
        xpath: str | None = None,
        desc: str = "",
    ) -> None:
        raw: dict[str, str | None] = {
            "acc_id": acc_id,
            "id": id,
            "text": text,
            "wx_id": wx_id,
            "wx": wx,
            "wx_tag": wx_tag,
            "css": css,
            "xpath": xpath,
        }
        chain = [Candidate(k, v) for k in STRATEGY_PRIORITY if (v := raw[k])]
        if not chain:
            raise LafError("Locator 至少需要一个候选定位策略")
        self.chain: list[Candidate] = chain
        self.desc: str = desc or str(chain[0])

    def __str__(self) -> str:
        return f"{self.desc}[" + " → ".join(str(c) for c in self.chain) + "]"
