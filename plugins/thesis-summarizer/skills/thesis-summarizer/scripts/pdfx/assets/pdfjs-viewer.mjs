// PDF.js viewer for the experimental self-contained HTML output.
const rightPane = document.querySelector('.col-right');
const pageNodes = [...document.querySelectorAll('.pdfpage[data-page]')];
const cropNodes = [...document.querySelectorAll('.pdfjs-crop[data-page][data-crop]')];

function bytesFromScript(id) {
  const encoded = document.getElementById(id)?.textContent.trim();
  if (!encoded) throw new Error(`Missing embedded resource: ${id}`);
  const binary = atob(encoded);
  return Uint8Array.from(binary, character => character.charCodeAt(0));
}

async function moduleUrlFromGzip(id) {
  if (typeof DecompressionStream !== 'function') {
    throw new Error('このブラウザはPDF.jsの展開に対応していません');
  }
  const compressed = bytesFromScript(id);
  const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'));
  const source = await new Response(stream).blob();
  return URL.createObjectURL(new Blob([source], { type: 'text/javascript' }));
}

function showError(message, pageNode) {
  const target = pageNode?.querySelector('.page-surface') || rightPane;
  const warning = document.createElement('p');
  warning.className = 'pdfjs-error';
  warning.textContent = message;
  target.append(warning);
}

async function start() {
  const [mainUrl, workerUrl] = await Promise.all([
    moduleUrlFromGzip('pdfjs-main-gzip'),
    moduleUrlFromGzip('pdfjs-worker-gzip'),
  ]);
  const pdfjs = await import(mainUrl);
  pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
  const data = bytesFromScript('pdf-source-data');
  const pdf = await pdfjs.getDocument({ data, useSystemFonts: true }).promise;

  const pageJobs = new Map();
  function renderPage(pageNode) {
    if (pageJobs.has(pageNode)) return pageJobs.get(pageNode);
    const job = (async () => {
      pageNode.dataset.renderState = 'loading';
      let canvas;
      try {
        const pageNumber = Number(pageNode.dataset.page) + 1;
        const page = await pdf.getPage(pageNumber);
        const viewport = page.getViewport({ scale: 165 / 72 });
        canvas = document.createElement('canvas');
        canvas.width = Math.round(viewport.width);
        canvas.height = Math.round(viewport.height);
        canvas.setAttribute('aria-hidden', 'true');
        const context = canvas.getContext('2d', { alpha: false });
        if (!context) throw new Error('Canvasを作成できません');
        pageNode.querySelector('.page-surface').append(canvas);
        await page.render({ canvasContext: context, canvas, viewport }).promise;
        pageNode.dataset.renderState = 'ready';
        page.cleanup();
        return canvas;
      } catch (error) {
        canvas?.remove();
        pageNode.dataset.renderState = 'error';
        showError(`原文の表示に失敗しました: ${error.message}`, pageNode);
        return null;
      }
    })();
    pageJobs.set(pageNode, job);
    return job;
  }

  async function renderCrop(crop) {
    try {
      const pageNode = pageNodes.find(node => node.dataset.page === crop.dataset.page);
      if (!pageNode) throw new Error('図の原文ページがありません');
      const source = await renderPage(pageNode);
      if (!source) throw new Error('図の原文ページを表示できません');
      const [x, y, width, height] = crop.dataset.crop.split(',').map(Number);
      const sourceX = Math.round(source.width * x / 100);
      const sourceY = Math.round(source.height * y / 100);
      const sourceRight = Math.round(source.width * (x + width) / 100);
      const sourceBottom = Math.round(source.height * (y + height) / 100);
      crop.width = Math.max(1, sourceRight - sourceX);
      crop.height = Math.max(1, sourceBottom - sourceY);
      const context = crop.getContext('2d');
      if (!context) throw new Error('図のCanvasを作成できません');
      context.drawImage(source, sourceX, sourceY,
        crop.width, crop.height, 0, 0, crop.width, crop.height);
    } catch (error) {
      const warning = document.createElement('span');
      warning.className = 'pdfjs-error';
      warning.textContent = `図の表示に失敗しました: ${error.message}`;
      crop.replaceWith(warning);
    }
  }

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        observer.unobserve(entry.target);
        void renderPage(entry.target);
      }
    }, { root: rightPane, rootMargin: '900px 0px' });
    pageNodes.forEach(node => observer.observe(node));
  } else {
    pageNodes.forEach(node => void renderPage(node));
  }
  cropNodes.forEach(crop => void renderCrop(crop));
}

start().catch(error => showError(`PDF.jsを起動できませんでした: ${error.message}`));
