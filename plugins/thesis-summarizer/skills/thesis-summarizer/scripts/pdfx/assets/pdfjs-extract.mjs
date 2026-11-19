// Experimental text/geometry extraction with the vendored PDF.js runtime.
// Node has no DOM canvas. Text extraction works with these unused DOM types
// present; page rendering is deferred to the browser viewer.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { gunzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

globalThis.DOMMatrix ??= class DOMMatrix {};
globalThis.ImageData ??= class ImageData {};
globalThis.Path2D ??= class Path2D {};

const [pdfArgument, workArgument] = process.argv.slice(2);
if (!pdfArgument || !workArgument) {
  throw new Error('usage: node pdfjs-extract.mjs <paper.pdf> <workdir>');
}
const pdfPath = resolve(pdfArgument);
const workdir = resolve(workArgument);
const vendor = resolve(fileURLToPath(new URL('.', import.meta.url)), 'pdfjs');
const moduleUrl = name => 'data:text/javascript;base64,' +
  gunzipSync(readFileSync(join(vendor, name))).toString('base64');
const pdfjs = await import(moduleUrl('pdf.min.mjs.gz'));
pdfjs.GlobalWorkerOptions.workerSrc = moduleUrl('pdf.worker.min.mjs.gz');
const pdfData = readFileSync(pdfPath);
const pdf = await pdfjs.getDocument({
  data: new Uint8Array(pdfData),
  useSystemFonts: true,
}).promise;

mkdirSync(join(workdir, 'text'), { recursive: true });
mkdirSync(join(workdir, 'out'), { recursive: true });

const sizes = [];
const units = [];
const MAX_UNIT_CHARS = 120;

function itemBox(item, style, viewport) {
  if (!item.str.trim() || !Number.isFinite(item.height) || !Number.isFinite(item.width)
      || item.height <= 0 || item.width <= 0) return null;
  const transform = pdfjs.Util.transform(viewport.transform, item.transform);
  const size = Math.hypot(transform[2], transform[3]) || item.height;
  const advanceX = transform[0] / size * item.width;
  const advanceY = transform[1] / size * item.width;
  const ascent = Number.isFinite(style?.ascent) ? style.ascent : 0.8;
  const descent = Number.isFinite(style?.descent) ? style.descent : -0.2;
  const points = [];
  for (const horizontal of [0, 1]) {
    for (const vertical of [ascent, descent]) {
      points.push([
        transform[4] + horizontal * advanceX + vertical * transform[2],
        transform[5] + horizontal * advanceY + vertical * transform[3],
      ]);
    }
  }
  const xs = points.map(point => point[0]);
  const ys = points.map(point => point[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

function rectangle(items, styles, viewport) {
  const boxes = items.map(item => itemBox(item, styles[item.fontName], viewport)).filter(Boolean);
  if (!boxes.length) return [];
  const left = Math.min(...boxes.map(box => box[0]));
  const top = Math.min(...boxes.map(box => box[1]));
  const right = Math.max(...boxes.map(box => box[2]));
  const bottom = Math.max(...boxes.map(box => box[3]));
  const round = value => Math.round(value * 100) / 100;
  return [[
    round(left / viewport.width * 100),
    round(top / viewport.height * 100),
    round((right - left) / viewport.width * 100),
    round((bottom - top) / viewport.height * 100),
  ]];
}

for (let page0 = 0; page0 < pdf.numPages; page0 += 1) {
  const page = await pdf.getPage(page0 + 1);
  const viewport = page.getViewport({ scale: 1 });
  sizes.push([viewport.width, viewport.height]);
  const { items, styles } = await page.getTextContent();
  const lines = [];
  let line = [];
  function saveLine() {
    const text = line.map(item => item.str).join('').trim();
    if (text) {
      let chunk = [];
      let length = 0;
      function saveChunk() {
        const chunkText = chunk.map(item => item.str).join('').trim();
        if (chunkText) {
          const rects = rectangle(chunk, styles, viewport);
          if (rects.length) {
            const unit = {
              id: `s${page0 + 1}.${lines.length + 1}`,
              page: page0,
              text: chunkText,
              rects,
            };
            lines.push(unit);
            units.push(unit);
          }
        }
        chunk = [];
        length = 0;
      }
      for (const item of line) {
        if (length >= 48 && length + item.str.length > MAX_UNIT_CHARS) saveChunk();
        chunk.push(item);
        length += item.str.length;
      }
      saveChunk();
    }
    line = [];
  }
  for (const item of items) {
    line.push(item);
    if (item.hasEOL) saveLine();
  }
  saveLine();
  writeFileSync(join(workdir, 'text', `p${String(page0 + 1).padStart(2, '0')}.txt`),
    lines.map(unit => unit.text).join('\n') + '\n');
  page.cleanup();
}

writeFileSync(join(workdir, 'sources.json'), JSON.stringify({ version: 2, units }, null, 1));
writeFileSync(join(workdir, 'pdfx.json'), JSON.stringify({
  pdf: pdfPath,
  pdf_sha256: createHash('sha256').update(pdfData).digest('hex'),
  backend: 'pdfjs',
  pages: pdf.numPages,
  sizes,
}, null, 2));
console.log(`${pdf.numPages} pages, ${units.length} source units (PDF.js)`);
