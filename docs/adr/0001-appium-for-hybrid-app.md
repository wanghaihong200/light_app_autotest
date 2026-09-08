# 混合 App 驱动选 Appium + UiAutomator2 driver

被测混合 App 含大量 WebView，原生↔WebView 切换是核心能力。选 Appium（Python 客户端 + UiAutomator2 driver）：context 切换内建、chromedriver 在底层经 CDP 驱动 WebView DOM、企业级生态（Grid 并行、W3C 协议）最全。代价是单步操作比直连方案慢（100~300ms 级）与环境重（CI 需 Node），靠显式等待策略治理，不为此换引擎。

## Considered Options

- **uiautomator2（openatx）+ 自封 CDP**：更快更轻，但不做 WebView DOM 操作，需自研 mini-chromedriver，对 WebView-heavy 应用是无底洞且只有自己维护。拒绝。
- **Airtest（图像识别）**：仅适用于拿不到控件树的场景（游戏/加壳），与本场景不符。拒绝。

## Consequences

- CI 节点必须装 Node + Appium Server + UiAutomator2 driver，环境初始化要脚本化。
- 若未来产品线出现 iOS 版本，Appium 侧可换 XCUITest driver 复用上层，这是保留口子而非当前承诺（iOS 当前为非目标）。
