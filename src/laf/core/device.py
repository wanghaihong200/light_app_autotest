"""本机多设备管理与按 worker 分配（xdist 一设备一 worker）。"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Device:
    udid: str
    state: str = "device"
    model: str = ""

    @property
    def usable(self) -> bool:
        return self.state == "device"


def parse_adb_devices(output: str) -> list[Device]:
    """解析 `adb devices -l` 输出。仅保留 device 状态行。"""
    devices: list[Device] = []
    for line in output.splitlines()[1:]:
        line = line.strip()
        if not line or not line.split():
            continue
        parts = line.split()
        udid, state = parts[0], parts[1]
        model = ""
        for p in parts[2:]:
            if p.startswith("model:"):
                model = p.removeprefix("model:")
                break
        devices.append(Device(udid=udid, state=state, model=model))
    return devices


def list_adb_devices(adb_bin: str = "adb") -> list[Device]:
    """调用本机 adb 枚举设备；adb 不可用时报含指引的错误。"""
    try:
        out = subprocess.run(
            [adb_bin, "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"找不到 {adb_bin} 命令：请安装 Android platform-tools 并加入 PATH"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"adb devices 失败: {exc.stderr}") from exc
    return [d for d in parse_adb_devices(out) if d.usable]


class DevicePool:
    """把本机设备确定性地分配给各 xdist worker（gw0→第1台，gw1→第2台…循环）。

    同一设备不重复分配给同批次 worker：分配按 worker 序号对设备数取模，
    因此 worker 数 ≤ 设备数时一一对应，> 设备数时多 worker 共享设备（串行让位给 xdist 互斥由设备锁保证的场景不做——骨架阶段取模即可）。
    """

    def __init__(self, devices: list[Device]) -> None:
        self.devices = [d for d in devices if d.usable]

    def allocate(self, worker_id: str | None = None) -> Device:
        if not self.devices:
            raise RuntimeError("没有可用的本机设备：请连接测试机并确认 adb devices 可见")
        if worker_id is None:
            worker_id = os.environ.get("PYTEST_XDIST_WORKER")
        index = _worker_index(worker_id)
        return self.devices[index % len(self.devices)]


def _worker_index(worker_id: str | None) -> int:
    """gw12 → 12；无 worker（单进程）→ 0。"""
    if not worker_id or not worker_id.startswith("gw"):
        return 0
    digits = worker_id[2:]
    return int(digits) if digits.isdigit() else 0
