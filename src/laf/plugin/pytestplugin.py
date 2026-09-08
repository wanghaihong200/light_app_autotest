"""pytest 插件：配置/设备/驱动 fixture、失败现场包、定位器纪律 lint。

约定：验收用例放 testcases/（lint 生效区），框架自身测试放 tests/（不受 lint）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from ..config.loader import load_config_file
from ..config.model import FrameworkConfig
from ..core.device import DevicePool, list_adb_devices
from ..core.driver import Driver, DriverContext
from ..core.errors import ConfigError
from ..core.flow import Flow
from ..evidence.capture import capture_failure
from ..factory import create_driver

#: testcases/ 中禁止的模式：定位器只能在 Page.LOCATORS 中声明（ADR-0004）
_LINT_PATTERNS = (r"\bLocator\s*\(", r"\.find\s*\(")


def lint_violations(filename: str, source: str) -> list[str]:
    violations: list[str] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pattern in _LINT_PATTERNS:
            if re.search(pattern, line):
                violations.append(
                    f"{filename}:{lineno}: 定位细节禁止出现在用例中（{stripped.strip()}）；"
                    "请声明到 Page.LOCATORS（ADR-0004）"
                )
                break
    return violations


# -- 命令行选项 -----------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("laf")
    group.addoption("--laf-profiles", default="profiles/apps.yaml",
                    help="产品线 profile 配置文件路径")
    group.addoption("--laf-app", default=None, help="被测 app id（profiles 里的键）")
    group.addoption("--laf-env", default="test", help="目标环境（默认 test）")
    group.addoption("--laf-udid", default=None, help="钉死设备 udid（默认自动分配）")
    group.addoption("--laf-artifacts", default=None, help="失败现场包目录（默认取配置）")


# -- 定位器纪律 lint（仅 testcases/） --------------------------------------


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    seen: set[str] = set()
    violations: list[str] = []
    for item in items:
        path = Path(str(item.path))
        if "testcases" not in path.parts or path.suffix != ".py" or path in seen:
            continue
        seen.add(path)
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:  # pragma: no cover
            continue
        violations.extend(lint_violations(str(path), source))
    if violations:
        raise pytest.UsageError("定位器纪律违规（ADR-0004）:\n  " + "\n  ".join(violations))


# -- fixtures --------------------------------------------------------------


@pytest.fixture(scope="session")
def laf_config(request: pytest.FixtureRequest) -> FrameworkConfig:
    profiles = request.config.getoption("--laf-profiles")
    return load_config_file(profiles)


@pytest.fixture(scope="session")
def laf_device(request: pytest.FixtureRequest, laf_config: FrameworkConfig):
    """按 xdist worker 分配本机设备；--laf-udid 钉死时优先。"""
    udid = request.config.getoption("--laf-udid")
    if udid:
        from ..core.device import Device

        return Device(udid=udid)
    pool = DevicePool(list_adb_devices())
    return pool.allocate()


@pytest.fixture(scope="session")
def driver(request: pytest.FixtureRequest, laf_config: FrameworkConfig) -> Driver:
    """会话级驱动：按 --laf-app/--laf-env 构建、启动，结束时释放。

    设备只在 app 端需要；小程序端（DevTools）不碰 adb，无测试机也能跑。
    """
    app_id: str | None = request.config.getoption("--laf-app")
    if not app_id:
        raise ConfigError(
            "未指定被测 app：请加 --laf-app <app_id>（可选 --laf-env，默认 test）"
        )
    env: str = request.config.getoption("--laf-env")
    options: dict[str, Any] = laf_config.build_options(app_id, env)

    device = None
    if options["kind"] == "app":
        from ..core.device import Device

        udid = request.config.getoption("--laf-udid")
        if udid:
            device = Device(udid=udid)
        else:
            device = DevicePool(list_adb_devices()).allocate()

    ctx = DriverContext(app_id=app_id, env=env, device=device, options=options)
    drv = create_driver(ctx)
    drv.start()
    yield drv
    drv.stop()


@pytest.fixture(scope="session")
def flow(driver: Driver) -> Flow:
    """业务流程入口：flow.page(HomePage) 获取本端页面实现。"""
    return Flow(driver)


# -- 失败现场包 ------------------------------------------------------------


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: Any):  # noqa: ANN001
    outcome = yield
    rep = outcome.get_result()
    if rep.when != "call" or not rep.failed:
        return
    driver: Driver | None = getattr(item, "funcargs", {}).get("driver")
    artifacts = item.config.getoption("--laf-artifacts") or "artifacts"
    capture_failure(driver, item.nodeid, artifacts_dir=str(artifacts))
