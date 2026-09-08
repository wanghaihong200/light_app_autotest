"""设备解析与分配单元测试（不依赖真实 adb）。"""

import pytest

from laf.core.device import Device, DevicePool, parse_adb_devices

ADB_OUTPUT = """\
List of devices attached
ceu0217253001080492     device product:star2q model:M2012K11AC device:star2q
emulator-5554           offline
192.168.1.5:5555        device product:atv model:SHIELD_TV device:atv
"""


def test_parse_keeps_only_usable():
    devices = parse_adb_devices(ADB_OUTPUT)
    usable = [d for d in devices if d.usable]
    assert [d.udid for d in usable] == ["ceu0217253001080492", "192.168.1.5:5555"]
    assert usable[0].model == "M2012K11AC"


def test_pool_allocates_by_worker_round_robin():
    pool = DevicePool(
        [Device("d1"), Device("d2", state="offline"), Device("d3")]
    )
    assert pool.allocate("gw0").udid == "d1"
    assert pool.allocate("gw1").udid == "d3"   # offline 的 d2 被跳过
    assert pool.allocate("gw2").udid == "d1"   # 循环


def test_pool_without_worker_uses_first():
    pool = DevicePool([Device("d1"), Device("d2")])
    assert pool.allocate().udid == "d1"


def test_pool_empty_raises():
    with pytest.raises(RuntimeError, match="没有可用的本机设备"):
        DevicePool([Device("d1", state="offline")]).allocate()
