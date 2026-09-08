# light_app_autotest（laf）

产品线 UI 自动化测试框架：**混合 App（原生+WebView）+ 微信小程序**，预留鸿蒙。

设计决策见 [CONTEXT.md](CONTEXT.md)（领域术语表）与 [docs/adr/](docs/adr/)（为什么这么做）。

## 架构（三层）

```
业务流程 Flow（端无关，一份）        ← testcases/ 编排
   │
页面实现 Page（每端一份）           ← testcases/pages/ 定位与操作
   │
驱动 Driver（SPI，每端一个）        ← src/laf/{appdriver,mpdriver}
   │                                   鸿蒙驱动（一年后）插在这里
Appium+UiAutomator2 / Node sidecar+官方automator SDK
```

- **候选链定位**：`Locator(id=…, text=…, css=…)` 自动按稳定性排序轮询，失败输出完整尝试轨迹
- **定位器纪律**：定位器只能声明在 `Page.LOCATORS`；`testcases/` 里出现 `Locator(` 或 `.find(` 会被 lint 拒绝
- **失败现场包**：用例失败自动落盘截图 + 页面快照到 `artifacts/`，并附加 Allure

## 环境准备

1. Python 3.12+：`pip install -e .`
2. Appium（混合 App 用）：`npm install -g appium && appium driver install uiautomator2`
3. Node.js（小程序 sidecar 用）：`cd node && npm install`
4. 微信开发者工具（小程序用）：开启服务端口（设置→安全）
5. Android platform-tools（adb）加入 PATH

## 编写用例

```python
# testcases/pages/mall_app.py —— 页面实现（每端一份）
from laf.core.locator import Locator
from laf.core.page import Page

class HomePage(Page):
    ready_marker = Locator(id="com.example.mall:id/tab_home", desc="首页tab")
    LOCATORS = {"search_box": Locator(id="…/search", text="搜索", css="#search")}

# testcases/test_home.py —— 用例（禁止定位细节，lint 强制）
def test_home(driver, flow):
    home = flow.page(HomePage)      # 换端时只需换成 MpHomePage
    home.wait_ready()
    assert home.has("search_box")
```

## 运行

```bash
cp profiles/apps.example.yaml profiles/apps.yaml   # 填产品线信息

# 混合 App（需 appium 服务 + 真机）
pytest testcases --laf-app mall --laf-env test -n 2     # -n 按设备分片并行

# 小程序（需 DevTools 已启动/可拉起）
pytest testcases --laf-app mall_mp --laf-env test

# 失败现场包在 artifacts/<用例>/；Allure 报告
allure serve allure-results
```

## 目录

```
src/laf/
  core/        Driver SPI、Locator 候选链、Page/Flow、设备池（引擎无关）
  appdriver/   混合 App 驱动（Appium；css 候选自动切 WebView 上下文）
  mpdriver/    小程序驱动（Node sidecar 客户端；wx* 策略）
  config/      YAML profile（App × 环境；设备是运行时事实不进配置）
  evidence/    失败现场包
  plugin/      pytest fixture、失败采集、定位器 lint
node/          sidecar：官方 miniprogram-automator 的 JSON-RPC 桥
testcases/     验收用例（lint 生效区）+ pages/ 页面实现
tests/unit/    框架自身单元测试（无设备可跑）
```

## 非目标（ADR 已裁定）

iOS 暂缓 · 设备农场 · 鸿蒙驱动（仅保证 SPI 可插入）· 真机生产微信自动化
