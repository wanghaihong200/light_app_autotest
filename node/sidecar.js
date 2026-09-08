#!/usr/bin/env node
/**
 * sidecar（ADR-0002）：官方 miniprogram-automator 的 JSON-RPC 桥。
 * 协议：一行一个 JSON 帧，请求 {id, method, params} → 响应 {id, result} | {id, error:{message}}。
 * 元素以句柄字符串（"h<n>"）暴露给 Python 侧，对象留在本进程内存中。
 */
const automator = require('miniprogram-automator');
const WebSocket = require('ws');

const args = process.argv.slice(2);
const portArgIdx = args.indexOf('--port');
const listenPort = portArgIdx >= 0 ? Number(args[portArgIdx + 1]) : 0;

let miniProgram = null; // automator 连接句柄
let currentPageCache = null;
const elements = new Map(); // handle -> Element
let nextHandle = 0;

function keepElement(el) {
  const handle = `h${nextHandle++}`;
  elements.set(handle, el);
  return handle;
}

function requirePage() {
  if (!miniProgram) throw new Error('小程序未连接：先调用 launch 或 connect');
  return miniProgram.currentPage();
}

const methods = {
  async launch({ project_path, devtools_cli, appid }) {
    const options = { projectPath: project_path };
    if (devtools_cli) options.cliPath = devtools_cli;
    if (appid) options.appid = appid; // 测试号 appid；缺省用工程配置
    miniProgram = await automator.launch(options);
    return true;
  },

  async connect({ ws_endpoint }) {
    miniProgram = await automator.connect({ wsEndpoint: ws_endpoint });
    return true;
  },

  async close() {
    if (miniProgram) {
      await miniProgram.close();
      miniProgram = null;
      elements.clear();
    }
    return true;
  },

  async current_page() {
    const page = await requirePage();
    return { path: page.path, query: page.query };
  },

  async navigate({ method, url }) {
    if (!miniProgram) throw new Error('小程序未连接');
    const allowed = ['reLaunch', 'switchTab', 'navigateTo', 'navigateBack'];
    if (!allowed.includes(method)) throw new Error(`不支持的路由方法: ${method}`);
    if (method === 'navigateBack') await miniProgram.navigateBack();
    else await miniProgram[method]({ url });
    return true;
  },

  async query({ selector }) {
    const page = await requirePage();
    const el = await page.$(selector);
    return el ? keepElement(el) : null;
  },

  async query_all({ selector }) {
    const page = await requirePage();
    const els = await page.$$(selector);
    return els.map(keepElement);
  },

  async find_by_text({ selector, text }) {
    const page = await requirePage();
    const els = await page.$$(selector || 'view');
    for (const el of els) {
      try {
        if ((await el.text()) === text) return keepElement(el);
      } catch (e) {
        /* 单个元素 text() 失败不中断遍历 */
      }
    }
    return null;
  },

  async element_tap({ handle }) {
    await elements.get(handle).tap();
    return true;
  },

  async element_input({ handle, value }) {
    await elements.get(handle).input(value);
    return true;
  },

  async element_text({ handle }) {
    return elements.get(handle).text();
  },

  async element_attribute({ handle, name }) {
    return elements.get(handle).attribute(name);
  },

  async element_size({ handle }) {
    const size = await elements.get(handle).size();
    return size; // {width, height}
  },

  async page_data({ path }) {
    const page = await requirePage();
    return path ? await page.data(path) : await page.data();
  },

  async call_wx_method({ method, args }) {
    if (!miniProgram) throw new Error('小程序未连接');
    return miniProgram.callWxMethod(method, ...(args || []));
  },

  async screenshot({ path }) {
    if (!miniProgram) throw new Error('小程序未连接');
    await miniProgram.screenshot({ path });
    return true;
  },

  async system_info() {
    if (!miniProgram) throw new Error('小程序未连接');
    return miniProgram.systemInfo();
  },

  async swipe({ x1, y1, x2, y2, duration }) {
    if (typeof miniProgram.swipe !== 'function') {
      throw new Error('当前 automator 版本不支持 swipe');
    }
    await miniProgram.swipe(x1, y1, x2, y2, duration);
    return true;
  },
};

const wss = new WebSocket.Server({ port: listenPort, host: '127.0.0.1' });
wss.on('listening', () => {
  const { port } = wss.address();
  // Python 侧靠这行拿端口，必须立即刷出
  process.stdout.write(`LAF_SIDECAR_PORT=${port}\n`);
});

wss.on('connection', (ws) => {
  ws.on('message', async (raw) => {
    let req;
    try {
      req = JSON.parse(raw.toString());
    } catch (e) {
      return;
    }
    const { id, method, params = {} } = req;
    const handler = methods[method];
    if (!handler) {
      ws.send(JSON.stringify({ id, error: { message: `未知方法: ${method}` } }));
      return;
    }
    try {
      const result = await handler(params);
      ws.send(JSON.stringify({ id, result }));
    } catch (e) {
      ws.send(JSON.stringify({ id, error: { message: String(e && e.message ? e.message : e) } }));
    }
  });
});
