"""定位器纪律 lint 单元测试（ADR-0004 的工具化）。"""

from laf.plugin.pytestplugin import lint_violations


def test_locator_in_test_case_is_violation():
    src = '''
def test_pay(flow):
    btn = flow.driver.find(Locator(id="x"))
'''
    violations = lint_violations("testcases/test_pay.py", src)
    assert len(violations) == 1
    assert "ADR-0004" in violations[0]
    assert "testcases/test_pay.py:3" in violations[0]


def test_clean_test_case_passes():
    src = '''
def test_pay(flow):
    flow.add_to_cart("sku-1")
    assert flow.page(CartPage).has("submit_btn")
'''
    assert lint_violations("testcases/test_pay.py", src) == []


def test_locator_in_comment_is_ignored():
    src = '''
# 曾用 Locator(id="x")，已迁移到 Page.LOCATORS
def test_pay(flow):
    flow.pay()
'''
    assert lint_violations("testcases/test_pay.py", src) == []


def test_multiple_violations_all_reported():
    src = '''
def test_a(flow):
    x = flow.driver.find(Locator(text="a"))
    y = Locator(css=".b")
'''
    assert len(lint_violations("t.py", src)) == 2
