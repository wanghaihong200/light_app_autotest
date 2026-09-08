"""配置模型与加载单元测试。"""

import pytest

from laf.config.loader import load_config_str
from laf.core.errors import ConfigError

YAML = """
defaults:
  appium_server: http://127.0.0.1:4723
  timeout: 7
apps:
  mall:
    kind: app
    android:
      package: com.example.mall
      activity: .MainActivity
    envs:
      test: {api_base: https://test.example.com}
  mall_mp:
    kind: miniprogram
    miniprogram:
      project_path: /tmp/mp
      devtools_cli: cli.bat
    envs:
      test: {api_base: https://test.example.com}
"""


def test_load_and_build_app_options():
    cfg = load_config_str(YAML)
    assert cfg.settings.timeout == 7
    opts = cfg.build_options("mall", "test")
    assert opts["kind"] == "app"
    assert opts["package"] == "com.example.mall"
    assert opts["appium_server"] == "http://127.0.0.1:4723"
    assert opts["env_vars"]["api_base"] == "https://test.example.com"


def test_load_and_build_mp_options():
    cfg = load_config_str(YAML)
    opts = cfg.build_options("mall_mp", "test")
    assert opts["kind"] == "miniprogram"
    assert opts["project_path"] == "/tmp/mp"
    assert opts["node_bin"] == "node"


def test_unknown_app_lists_available():
    cfg = load_config_str(YAML)
    with pytest.raises(ConfigError, match="mall_mp"):
        cfg.build_options("nope", "test")


def test_unknown_env_lists_available():
    cfg = load_config_str(YAML)
    with pytest.raises(ConfigError, match="test"):
        cfg.build_options("mall", "staging")


def test_app_without_android_rejected():
    with pytest.raises(ConfigError, match="android"):
        load_config_str(
            "apps:\n  bad:\n    kind: app\n    envs: {test: {}}\n"
        )
