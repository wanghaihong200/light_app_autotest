"""商城微信小程序的页面实现示例。"""

from laf.core.locator import Locator
from laf.core.page import Page


class MpHomePage(Page):
    """小程序首页。"""

    ready_marker = Locator(wx_tag="view", wx="home-swiper", desc="首页轮播")

    LOCATORS = {
        "search_bar": Locator(
            wx_id="searchBar",
            wx="search-bar",
            text="搜索",
            desc="搜索栏",
        ),
    }
