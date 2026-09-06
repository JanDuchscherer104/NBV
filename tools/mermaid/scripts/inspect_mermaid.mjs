#!/usr/bin/env node
/** Inspect an already-rendered SVG; this is not a second Mermaid renderer. */
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import puppeteer from 'puppeteer';

const [input, widthArg = '160', outputArg] = process.argv.slice(2);
const widthMm = Number(widthArg);
if (!input || !Number.isFinite(widthMm) || widthMm <= 0) {
  throw new Error('usage: inspect_mermaid.mjs figure.svg [width-mm=160] [output-prefix]');
}
const output = outputArg ?? input.replace(/\.svg$/i, '');
await fs.mkdir(path.dirname(output), { recursive: true });
const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1200, deviceScaleFactor: 2 });
  await page.goto(pathToFileURL(path.resolve(input)).href, { waitUntil: 'networkidle0' });
  // Reuse the CLI's installed KaTeX CSS when inspecting its exported SVG.
  // Font bytes stay in this transient browser DOM; no font assets are written.
  const katexPath = new URL('../node_modules/katex/dist/katex.min.css', import.meta.url);
  let css = await fs.readFile(katexPath, 'utf8');
  const fontUrls = [...new Set([...css.matchAll(/url\(([^)]+)\)/g)].map(m => m[1]))];
  for (const url of fontUrls) {
    const name = url.replace(/^['"]|['"]$/g, '');
    if (!name.startsWith('fonts/')) throw new Error(`unexpected KaTeX font URL: ${name}`);
    const font = await fs.readFile(new URL(name, katexPath));
    const mime = name.endsWith('.woff2') ? 'font/woff2' : name.endsWith('.woff') ? 'font/woff' : 'font/ttf';
    css = css.split(`url(${url})`).join(`url(data:${mime};base64,${font.toString('base64')})`);
  }
  await page.evaluate((css) => {
    const style = document.createElementNS('http://www.w3.org/2000/svg', 'style');
    style.textContent = css;
    document.documentElement.prepend(style);
  }, css);
  await page.evaluate(() => document.fonts.ready);
  const report = await page.evaluate((widthMm) => {
    const svg = document.querySelector('svg');
    if (!svg) throw new Error('no SVG');
    const box = svg.viewBox.baseVal;
    const scalePt = widthMm * 72 / 25.4 / box.width;
    svg.style.maxWidth = 'none';
    svg.style.width = `${box.width}px`;
    svg.style.height = `${box.height}px`;
    const rect = el => {
      const r = el.getBoundingClientRect();
      return { x: r.x, y: r.y, width: r.width, height: r.height };
    };
    const errors = [];
    const nodes = [...document.querySelectorAll('g.node')].map(el => {
      const shape = el.querySelector(':scope > rect, :scope > polygon, :scope > path');
      const label = el.querySelector('.label');
      const title = el.querySelector('b');
      if (!shape || !label || !title) {
        errors.push(`${el.id}: missing shape, label or bold title`);
        return null;
      }
      const a = rect(shape), b = rect(label);
      const titleBounds = rect(title);
      const math = el.querySelector('.katex');
      if (math && rect(math).y < titleBounds.y + titleBounds.height - 1) {
        errors.push(`${el.id}: math is not below the title`);
      }
      const font = getComputedStyle(title);
      const body = getComputedStyle(el.querySelector('.nodeLabel') ?? label);
      const titlePt = parseFloat(font.fontSize) * scalePt;
      const bodyPt = parseFloat(body.fontSize) * scalePt;
      if (titlePt < 11 || bodyPt < 9) errors.push(`${el.id}: undersized type ${titlePt.toFixed(2)}/${bodyPt.toFixed(2)} pt`);
      if (parseInt(font.fontWeight) < 700) errors.push(`${el.id}: title is not bold`);
      if (parseFloat(font.fontSize) < 1.15 * parseFloat(body.fontSize)) errors.push(`${el.id}: weak title hierarchy`);
      if (b.x < a.x - 1 || b.y < a.y - 1 || b.x+b.width > a.x+a.width+1 || b.y+b.height > a.y+a.height+1) errors.push(`${el.id}: label exceeds node bounds`);
      return { id: el.id, title: title.textContent, titlePt, bodyPt, shape: a, label: b };
    }).filter(Boolean);
    for (let i=0; i<nodes.length; i++) for (let j=i+1; j<nodes.length; j++) {
      const a=nodes[i].shape, b=nodes[j].shape;
      const overlapX=Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x);
      const overlapY=Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y);
      if (overlapX > 2 && overlapY > 2) errors.push(`overlapping nodes: ${nodes[i].id}, ${nodes[j].id}`);
    }
    const edgePoints = [...document.querySelectorAll('.edgeLabel')]
      .filter(el => el.textContent.trim())
      .map(el => parseFloat(getComputedStyle(el).fontSize)*scalePt);
    if (edgePoints.some(pt => pt<8)) errors.push('edge label below 8 pt');
    if (!nodes.length) errors.push('no inspected nodes');
    if (document.querySelector('.katex-error')) errors.push('KaTeX error');
    if (document.querySelector('.katex') && !document.querySelector('.katex-html')) errors.push('expected KaTeX HTML math, not native MathML');
    if (document.documentElement.textContent.includes('$$')) errors.push('unrendered math delimiter');
    const heightMm=widthMm*box.height/box.width;
    if (heightMm>230) errors.push(`figure height ${heightMm.toFixed(1)} mm exceeds 230 mm`);
    return { widthMm, heightMm, svgWidth:box.width, svgHeight:box.height,
      minTitlePt:Math.min(...nodes.map(n=>n.titlePt)), minBodyPt:Math.min(...nodes.map(n=>n.bodyPt)),
      minEdgePt:edgePoints.length ? Math.min(...edgePoints):null,
      nodeAreaFraction:nodes.reduce((s,n)=>s+n.shape.width*n.shape.height,0)/(box.width*box.height),
      nodes, errors };
  }, widthMm);
  const client = await page.createCDPSession();
  await client.send('DOM.enable');
  await client.send('CSS.enable');
  const { root } = await client.send('DOM.getDocument');
  const { nodeId } = await client.send('DOM.querySelector', { nodeId: root.nodeId, selector: 'g.node b' });
  const { fonts } = nodeId ? await client.send('CSS.getPlatformFontsForNode', { nodeId }) : { fonts: [] };
  report.titleFonts = fonts;
  const { nodeId: mathId } = await client.send('DOM.querySelector', { nodeId: root.nodeId, selector: '.katex-html' });
  report.mathFonts = mathId ? (await client.send('CSS.getPlatformFontsForNode', { nodeId: mathId })).fonts : [];
  if (mathId && !report.mathFonts.some(f => f.familyName.startsWith('KaTeX') && f.glyphCount > 0)) report.errors.push('KaTeX font fallback detected');
  if (!fonts.some(f => f.familyName === 'CMU Serif' && f.glyphCount > 0)) report.errors.push('CMU Serif not used for title glyphs');
  const svg = await page.$('svg');
  await page.evaluate((widthMm) => {
    const svg = document.querySelector('svg');
    svg.style.width = `${widthMm * 96 / 25.4}px`;
    svg.style.height = 'auto';
  }, widthMm);
  await svg.screenshot({ path: output+'.png' });
  await page.evaluate(() => { document.querySelector('svg').style.filter = 'grayscale(1)'; });
  await svg.screenshot({ path: output+'.gray.png' });
  await fs.writeFile(output+'.qa.json', JSON.stringify(report, null, 2)+'\n');
  console.log(JSON.stringify({ input, ...report, nodes: report.nodes.length }, null, 2));
  if (report.errors.length) process.exitCode = 1;
} finally {
  await browser.close();
}
