# 小程序驱动经 Node sidecar 桥接官方 automator SDK

微信官方 miniprogram-automator SDK 只有 Node.js 版，而框架核心是 Python/pytest。决定内置一个约 200 行的 Node sidecar 进程：内部用官方 SDK 操作小程序（DevTools 自动化端口），对外暴露本地 JSON-RPC 接口供 Python 调用。协议忠实度由官方 SDK 保证，微信升级只需升 npm 包。

## Considered Options

- **纯 Python 直连 automator WebSocket 协议**：架构干净，但约 40 个协议方法的兼容风险自担。拒绝。
- **小程序用例直接用 JS 写**：与"业务流程跨端复用"（ADR-0003）冲突。拒绝。

## Consequences

- Python 仓库中会出现 Node 代码，属刻意设计；sidecar 与 Appium Server 同为 CI 上的 Node 进程，无新增环境成本。
- 真机调试 2.0 仅保留 `connect(wsEndpoint)` 口子，手工触发、不进 CI（微信无生产微信真机自动化通道，为安全设计，不试图绕过）。
