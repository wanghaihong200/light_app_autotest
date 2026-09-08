"""混合 App 用例示例（lint 生效区：只允许 page.on/has，禁止定位细节）。

跑法：appium 服务就绪 + 真机连接 + profiles/apps.yaml 配好，然后
    pytest testcases/test_demo_app.py --laf-app mall --laf-env test
"""

import pytest

from pages.mall_app import CartPage, HomePage

pytestmark = pytest.mark.skip(reason="骨架示例：填好 profiles/apps.yaml 并连接真机后移除")


@pytest.mark.app
@pytest.mark.real_device
def test_open_home_and_search(driver, flow):
    home = flow.page(HomePage)
    home.wait_ready()
    assert home.has("search_box"), "首页搜索框未出现"


@pytest.mark.app
@pytest.mark.real_device
def test_cart_ready(driver, flow):
    cart = flow.page(CartPage)
    cart.wait_ready()
    submit = cart.on("submit_btn")
    assert submit.is_visible()
