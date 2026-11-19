// PDF.js viewer for the experimental self-contained HTML output.
const rightPane = document.querySelector('.col-right');
const pageNodes = [...document.querySelectorAll('.pdfpage[data-page]')];

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

  async function renderPage(pageNode) {
    if (pageNode.dataset.renderState) return;
    pageNode.dataset.renderState = 'loading';
    try {
      const pageNumber = Number(pageNode.dataset.page) + 1;
      const page = await pdf.getPage(pageNumber);
      const viewport = page.getViewport({ scale: 165 / 72 });
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(viewport.width);
      canvas.height = Math.round(viewport.height);
      canvas.setAttribute('aria-hidden', 'true');
      const context = canvas.getContext('2d', { alpha: false });
      if (!context) throw new Error('Canvasを作成できません');
      pageNode.querySelector('.page-surface').append(canvas);
      await page.render({ canvasContext: context, canvas, viewport }).promise;
      pageNode.dataset.renderState = 'ready';
      page.cleanup();
    } catch (error) {
      pageNode.dataset.renderState = 'error';
      showError(`原文の表示に失敗しました: ${error.message}`, pageNode);
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
}

start().catch(error => showError(`PDF.jsを起動できませんでした: ${error.message}`));
