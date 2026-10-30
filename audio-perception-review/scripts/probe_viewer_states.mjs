// 逐输出帧采集 viewer 的实际选画状态（window.stepAt(t) 的返回值），供 check_av_sync.py 与音频对账。
// 用法（剧集目录，viewer 静态服务已启动）：node probe_viewer_states.mjs <viewer-url> <t0> <t1> <out.json>
import fs from 'node:fs';
import path from 'node:path';
import {puppeteerFor} from '../../draw-over-animation/scripts/pipeline.mjs';

const [url, t0, t1, out] = process.argv.slice(2);
const puppeteer = puppeteerFor(path.resolve('.'));
const browser = await puppeteer.launch({headless: 'new', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
const page = await browser.newPage();
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
await page.setViewport({width: 1280, height: 720});
await page.goto(url, {waitUntil: 'load'});
await page.waitForFunction('window.ready===true', {timeout: 120000});
const fps = 30, n = Math.round((Number(t1) - Number(t0)) * fps);
const states = await page.evaluate((t0, n, fps) => {
  const r = [];
  for (let i = 0; i < n; i++) { const t = t0 + i / fps; r.push({i, t, ...window.stepAt(t)}); }
  return r;
}, Number(t0), n, fps);
await browser.close();
if (errors.length) { console.error(errors.join('\n')); process.exit(1); }
fs.writeFileSync(out, JSON.stringify({url, fps, states}, null, 1));
console.log(`states ${states.length} -> ${out}`);
