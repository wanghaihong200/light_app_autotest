"""失败现场包（ADR 语境：报告的命根子）。

用例失败时收集：截图 + 页面结构快照，落盘到 artifacts/<nodeid>/，
并尽力附加到 Allure（未启用 Allure 时静默跳过）。
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.driver import Driver


def sanitize_nodeid(nodeid: str) -> str:
    """tests/test_x.py::test_y[param] → tests_test_x.py__test_y_param_"""
    return re.sub(r"[^\w.-]", "_", nodeid)


def capture_failure(
    driver: Driver | None,
    nodeid: str,
    artifacts_dir: str = "artifacts",
) -> list[str]:
    """尽力而为地采集现场：任何一步失败都不掩盖原始测试失败。"""
    if driver is None:
        return []
    out_dir = Path(artifacts_dir) / sanitize_nodeid(nodeid) / time.strftime("%Y%m%d_%H%M%S")
    written: list[str] = []
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        shot = str(out_dir / "screenshot.png")
        written.append(driver.screenshot(shot))
        dump = out_dir / "page_dump.txt"
        dump.write_text(driver.page_dump(), encoding="utf-8")
        written.append(str(dump))
    except Exception:  # noqa: BLE001 —— 现场采集失败不打扰原始失败
        return written
    _attach_allure(out_dir)
    return written


def _attach_allure(out_dir: Path) -> None:
    try:
        import allure
    except ImportError:
        return
    for f in sorted(out_dir.iterdir()):
        kind = "image/png" if f.suffix == ".png" else "text/plain"
        allure.attach.file(str(f), name=f.name, attachment_type=kind)
