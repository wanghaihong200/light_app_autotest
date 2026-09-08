"""小程序用例示例（DevTools 一级环境，进 CI）。

跑法：微信开发者工具已安装、profiles/apps.yaml 配好 project_path，然后
    pytest testcases/test_demo_mp.py --laf-app mall_mp --laf-env test
"""

import pytest

from pages.mall_mp import MpHomePage

pytestmark = pytest.mark.skip(reason="骨架示例：填好 profiles/apps.yaml 并启动 DevTools 后移除")


@pytest.mark.mp
def test_mp_home_ready(driver, flow):
    home = flow.page(MpHomePage)
    home.wait_ready()
    assert home.has("search_bar")
