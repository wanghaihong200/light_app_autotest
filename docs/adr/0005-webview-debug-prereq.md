# WebView 自动化的前置条件：被测包必须开启 WebView 调试

Appium 的 `WEBVIEW_*` 上下文依赖被测 App 暴露 chromedriver 调试 socket（`setWebContentsDebuggingEnabled(true)`，物理表现为 `/proc/net/unix` 中的 `devtools_remote` socket）。真机验证发现：release 构建的 heytap 浏览器加载网页后该 socket 数为 0（1008 个 unix socket 中无一 devtools），Appium 侧永远只见 `NATIVE_APP` 上下文。因此 **WebView 自动化只对开启调试的包成立**——产品线混合 App 的测试包（debug build 或显式开启调试）是框架的运行前提，需在 CI 环境说明与用例准入检查中体现。

## Consequences

- 上下文切换的框架逻辑由单元测试桩覆盖；真机复验以产品线 App（调试开启）为准，无需第三方浏览器替代。
- 准入检查建议：`adb shell cat /proc/net/unix | grep -c devtools` 在被测 App 打开 WebView 页后应 ≥1，为 0 则测试包未开调试，用例应当跳过并给出指引。
- 真机验证沉淀的两条设备约束已吸收进框架默认能力：`ignoreHiddenApiPolicyError`（ColorOS 拒 shell 写 secure settings）、`noReset`（ColorOS 禁 shell pm clear；亦符合"App 默认已登录"共识）。
