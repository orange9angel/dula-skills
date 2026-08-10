// Rasterize an SVG file/string to PNG via dula-engine's Puppeteer (ESM).
// Usage: node scripts/render_svg.js <input.svg> <output.png> [width] [height] [--transparent]
import { createRequire } from 'module';
import path from 'path';
const require = createRequire(import.meta.url);
const puppeteer = require('D:/opensource/movie/dula-engine/node_modules/puppeteer');

const args = process.argv.slice(2);
const transparent = args.includes('--transparent');
const [input, output, w = '1672', h = '941'] = args.filter((a) => !a.startsWith('--'));

const browser = await puppeteer.launch({ headless: 'new' });
const page = await browser.newPage();
await page.setViewport({ width: parseInt(w), height: parseInt(h), deviceScaleFactor: 1 });
await page.goto('file://' + path.resolve(input).replace(/\\/g, '/'));
await page.screenshot({ path: output, omitBackground: transparent });
await browser.close();
console.log('wrote', output);
