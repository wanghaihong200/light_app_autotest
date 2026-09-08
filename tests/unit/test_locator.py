"""Locator / 候选链单元测试。"""

import pytest

from laf.core.errors import LafError
from laf.core.locator import Candidate, Locator


def test_chain_follows_priority_order():
    loc = Locator(xpath="//x", css="#s", text="提交", id="com.x:id/btn")
    assert [c.strategy for c in loc.chain] == ["id", "text", "css", "xpath"]


def test_acc_id_has_highest_priority():
    loc = Locator(id="a", acc_id="搜索按钮", text="搜索")
    assert [c.strategy for c in loc.chain] == ["acc_id", "id", "text"]


def test_empty_locator_rejected():
    with pytest.raises(LafError):
        Locator()


def test_desc_defaults_to_first_candidate():
    loc = Locator(id="a", text="b")
    assert loc.desc == "id=a"


def test_str_shows_full_chain():
    loc = Locator(id="a", text="b", desc="提交按钮")
    s = str(loc)
    assert "提交按钮" in s
    assert "id=a" in s and "text=b" in s


def test_css_candidate_is_web():
    assert Candidate("css", "#x").is_web
    assert not Candidate("id", "x").is_web
