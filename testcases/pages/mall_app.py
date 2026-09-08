"""商城混合 App（Android）的页面实现示例。"""

from laf.core.page import Page
from laf.core.locator import Locator


class HomePage(Page):
    """首页。"""

    ready_marker = Locator(id="com.example.mall:id/tab_home", desc="首页 tab")

    LOCATORS = {
        # 候选链自动排序：id → text → css（css 会触发 WebView 上下文切换）
        "search_box": Locator(
            id="com.example.mall:id/search",
            text="搜索",
            css="#search",
            desc="搜索框",
        ),
    }


class CartPage(Page):
    """购物车。"""

    ready_marker = Locator(id="com.example.mall:id/cart_title", desc="购物车标题")

    LOCATORS = {
        "submit_btn": Locator(
            id="com.example.mall:id/submit",
            text="结算",
            desc="结算按钮",
        ),
    }
