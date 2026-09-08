"""sidecar 传输层（ADR-0002）：与 Node sidecar 的 WebSocket JSON-RPC 通信。

SubprocessSidecar 负责：拉起 `node sidecar.js` → 从 stdout 读取
`LAF_SIDECAR_PORT=<port>` → 建立连接。进程退出时 sidecar 自动关闭。
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from ..core.errors import DriverError

SIDECAR_JS = Path(__file__).resolve().parents[3] / "node" / "sidecar.js"
_PORT_LINE_PREFIX = "LAF_SIDECAR_PORT="


class SidecarError(DriverError):
    """sidecar 返回错误帧或通信失败。"""


class SidecarTransport:
    """同步请求/响应客户端。每次 call 一来一回，按 id 配对。"""

    def __init__(self, url: str, timeout: float = 120.0) -> None:
        import websocket  # websocket-client

        self._ws = websocket.create_connection(url, timeout=timeout)
        self._next_id = 0

    def call(self, method: str, **params: Any) -> Any:
        self._next_id += 1
        req_id = self._next_id
        self._ws.send(json.dumps({"id": req_id, "method": method, "params": params}))
        while True:
            raw = self._ws.recv()
            if not raw:
                raise SidecarError("sidecar 连接已关闭")
            frame = json.loads(raw)
            if frame.get("id") != req_id:
                continue  # 事件帧等暂不处理，只配对响应
            if "error" in frame:
                err = frame["error"]
                raise SidecarError(f"sidecar {method} 失败: {err.get('message', err)}")
            return frame.get("result")

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:  # noqa: BLE001
            pass


class SubprocessSidecar:
    """管理 sidecar 子进程生命周期：start() 后 .transport 可用。"""

    def __init__(self, node_bin: str = "node", sidecar_js: Path | None = None) -> None:
        self.node_bin = node_bin
        self.sidecar_js = Path(sidecar_js or SIDECAR_JS)
        self._proc: subprocess.Popen[str] | None = None
        self.transport: SidecarTransport | None = None

    def start(self) -> SidecarTransport:
        if self.transport is not None:
            return self.transport
        if not self.sidecar_js.exists():
            raise DriverError(f"sidecar 脚本不存在: {self.sidecar_js}")
        try:
            self._proc = subprocess.Popen(
                [self.node_bin, str(self.sidecar_js), "--port", "0"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
            )
        except FileNotFoundError as exc:
            raise DriverError(
                f"找不到 node（{self.node_bin}）：小程序驱动依赖 Node 运行 sidecar。"
                "请安装 Node.js 或在配置 defaults.node_bin 指定路径。"
            ) from exc
        port = self._read_port(timeout=20.0)
        self.transport = SidecarTransport(f"ws://127.0.0.1:{port}")
        return self.transport

    def _read_port(self, timeout: float) -> int:
        deadline = time.monotonic() + timeout
        proc = self._proc
        assert proc is not None and proc.stdout is not None
        reader = threading.Thread(target=self._drain_forever, daemon=True)
        reader.start()
        while time.monotonic() < deadline:
            port = getattr(self, "_port", None)
            if port is not None:
                return int(port)
            if proc.poll() is not None:
                raise DriverError(f"sidecar 进程提前退出（code={proc.returncode}）")
            time.sleep(0.05)
        raise DriverError(f"等待 sidecar 端口超时（{timeout}s）")

    def _drain_forever(self) -> None:
        """后台读 stdout：取到端口后继续吞输出，防止管道塞满阻塞子进程。"""
        proc = self._proc
        assert proc is not None and proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if line.startswith(_PORT_LINE_PREFIX) and not hasattr(self, "_port"):
                self._port = int(line.removeprefix(_PORT_LINE_PREFIX))

    def stop(self) -> None:
        if self.transport is not None:
            self.transport.close()
            self.transport = None
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover
                self._proc.kill()
            self._proc = None
