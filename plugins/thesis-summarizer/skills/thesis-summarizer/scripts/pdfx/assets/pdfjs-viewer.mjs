// PDF.js viewer for the self-contained HTML output.
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
  const textLayers = new Map();
  const textViewport = new Map();
  const nearPages = new Set();
  const deferredUnload = new Set();
  let selectingText = false;
  const resizeObserver = typeof ResizeObserver === 'function'
    ? new ResizeObserver(entries => {
      for (const entry of entries) {
        const pageNode = entry.target.closest('.pdfpage');
        const viewport = textViewport.get(pageNode);
        if (viewport) updateTextScale(pageNode, viewport);
      }
    }) : null;

  function updateTextScale(pageNode, viewport) {
    const surface = pageNode.querySelector('.page-surface');
    const width = surface.clientWidth;
    if (width > 0) {
      surface.style.setProperty('--total-scale-factor', width / viewport.rawDims.pageWidth);
    }
  }

  function activateSourceFromText(event) {
    if (!event.target.closest('.pdfjs-text-layer span')) return;
    const selection = window.getSelection();
    if (selection && !selection.isCollapsed) return;
    const pageNode = event.currentTarget.closest('.pdfpage');
    const hit = [...pageNode.querySelectorAll('.hl')].find(link => {
      const bounds = link.getBoundingClientRect();
      return event.clientX >= bounds.left && event.clientX <= bounds.right
        && event.clientY >= bounds.top && event.clientY <= bounds.bottom;
    });
    if (hit) {
      event.preventDefault();
      event.stopPropagation();
      hit.click();
    }
  }

  async function showTextLayer(pageNode) {
    if (textLayers.has(pageNode)) return;
    const state = { cancelled: false, layer: null, container: null };
    textLayers.set(pageNode, state);
    try {
      if (!await renderPage(pageNode) || state.cancelled) return;
      const page = await pdf.getPage(Number(pageNode.dataset.page) + 1);
      if (state.cancelled) return;
      const viewport = page.getViewport({ scale: 1 });
      const surface = pageNode.querySelector('.page-surface');
      const container = document.createElement('div');
      container.className = 'textLayer pdfjs-text-layer';
      container.setAttribute('aria-label', `原文PDF ${Number(pageNode.dataset.page) + 1}ページの選択可能な本文`);
      state.container = container;
      surface.append(container);
      updateTextScale(pageNode, viewport);
      textViewport.set(pageNode, viewport);
      resizeObserver?.observe(surface);
      const layer = new pdfjs.TextLayer({
        textContentSource: page.streamTextContent(), container, viewport,
      });
      state.layer = layer;
      container.addEventListener('click', activateSourceFromText);
      await layer.render();
      if (state.cancelled) return;
      pageNode.dataset.textState = 'ready';
    } catch (error) {
      if (!state.cancelled) {
        pageNode.dataset.textState = 'error';
        showError(`原文の文字選択を有効にできませんでした: ${error.message}`, pageNode);
      }
    }
  }

  function hideTextLayer(pageNode) {
    const state = textLayers.get(pageNode);
    if (!state) return;
    const selection = window.getSelection();
    if (selectingText || (selection && !selection.isCollapsed && selection.rangeCount
        && state.container && selection.getRangeAt(0).intersectsNode(state.container))) {
      deferredUnload.add(pageNode);
      return;
    }
    state.cancelled = true;
    state.layer?.cancel();
    state.container?.remove();
    textLayers.delete(pageNode);
    textViewport.delete(pageNode);
    resizeObserver?.unobserve(pageNode.querySelector('.page-surface'));
    deferredUnload.delete(pageNode);
    delete pageNode.dataset.textState;
  }

  function flushDeferredUnload() {
    for (const pageNode of deferredUnload) {
      if (nearPages.has(pageNode)) deferredUnload.delete(pageNode);
      else hideTextLayer(pageNode);
    }
  }
  document.addEventListener('pointerdown', event => {
    if (event.target.closest?.('.pdfjs-text-layer span')) selectingText = true;
  });
  for (const eventName of ['pointerup', 'pointercancel']) {
    window.addEventListener(eventName, () => {
      selectingText = false;
      flushDeferredUnload();
    });
  }
  document.addEventListener('selectionchange', () => {
    if (!selectingText) flushDeferredUnload();
  });

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
    const textObserver = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          nearPages.add(entry.target);
          deferredUnload.delete(entry.target);
          void showTextLayer(entry.target);
        } else {
          nearPages.delete(entry.target);
          hideTextLayer(entry.target);
        }
      }
    }, { root: rightPane, rootMargin: '300px 0px' });
    pageNodes.forEach(node => textObserver.observe(node));
  } else {
    pageNodes.forEach(node => void showTextLayer(node));
  }
  cropNodes.forEach(crop => void renderCrop(crop));
}

start().catch(error => showError(`PDF.jsを起動できませんでした: ${error.message}`));
