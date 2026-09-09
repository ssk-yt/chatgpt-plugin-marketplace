(function(){
  const anchors=JSON.parse(document.getElementById('anchor-data').textContent);
  const byId=Object.fromEntries(anchors.map(anchor=>[anchor.id,anchor]));
  const layout=document.querySelector('.layout');
  const left=document.querySelector('.col-left');
  const right=document.querySelector('.col-right');
  const pages=document.querySelector('.pdf-pages');
  const splitter=document.querySelector('.splitter');
  const mobileTabs=[...document.querySelectorAll('[data-mobile-view]')];
  const proseLinks=[...document.querySelectorAll('.a')];
  const mediaJumps=[...document.querySelectorAll('.media-jump')];
  const highlightGroups={};
  let selectedId='';
  let pinnedId='';
  let hoveredId='';
  let zoom=1;
  let glideFrame=0;
  let mobileFrame=0;

  const reducedMotion=()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const isMobile=()=>window.matchMedia('(max-width:900px)').matches;
  function setMobileState(pane){
    layout.dataset.mobilePane=pane;
    mobileTabs.forEach(tab=>tab.classList.toggle('active',tab.dataset.mobileView===pane));
  }
  function replacePaneHash(pane){
    const target=pane==='pdf'?'#pdf-pane':'#article-pane';
    if(location.hash!==target)history.replaceState(null,'',target);
  }
  function showMobilePane(pane,animate=true,updateHash=true){
    setMobileState(pane);
    if(!isMobile())return;
    const index=pane==='pdf'?1:0;
    layout.scrollTo({
      left:index*layout.clientWidth,
      behavior:reducedMotion()||!animate?'auto':'smooth'
    });
    if(updateHash)replacePaneHash(pane);
  }
  function cancelGlide(){if(glideFrame){cancelAnimationFrame(glideFrame);glideFrame=0;}}
  function glideWithin(scroller,target){
    cancelGlide();
    const destination=Math.max(0,target.getBoundingClientRect().top-scroller.getBoundingClientRect().top+scroller.scrollTop-scroller.clientHeight*.34);
    if(reducedMotion()){scroller.scrollTop=destination;return;}
    const start=scroller.scrollTop;
    const delta=destination-start;
    const duration=Math.max(420,Math.min(850,360+Math.abs(delta)*.42));
    const started=performance.now();
    function tick(now){
      const t=Math.min(1,(now-started)/duration);
      const eased=1-Math.pow(1-t,5);
      scroller.scrollTop=start+delta*eased;
      if(t<1)glideFrame=requestAnimationFrame(tick);else glideFrame=0;
    }
    glideFrame=requestAnimationFrame(tick);
  }
  function renderHighlightState(){
    const emphasisId=hoveredId||selectedId;
    proseLinks.forEach(link=>link.classList.toggle('pinned',link.dataset.anchor===pinnedId));
    document.querySelectorAll('.hl').forEach(hit=>hit.classList.toggle('emphasis',hit.dataset.anchor===emphasisId));
  }
  function selectPdf(id){
    selectedId=id;
    renderHighlightState();
  }
  function togglePinnedProse(id){
    const release=pinnedId===id;
    pinnedId=release?'':id;
    selectedId=release?'':id;
    renderHighlightState();
  }
  function clearSelection(){
    selectedId='';
    pinnedId='';
    hoveredId='';
    renderHighlightState();
  }
  function hydrateHighlights(){
    anchors.forEach(anchor=>{
      const hits=[...document.querySelectorAll('.hl[data-anchor="'+anchor.id+'"]')];
      highlightGroups[anchor.id]=hits;
      hits.forEach(hit=>{
        hit.addEventListener('click',event=>{
          event.preventDefault();
          togglePinnedProse(anchor.id);
          history.replaceState(null,'',hit.getAttribute('href'));
          const prose=proseLinks.find(link=>link.dataset.anchor===anchor.id);
          if(!prose)return;
          if(isMobile()){
            showMobilePane('article',true,false);
            requestAnimationFrame(()=>glideWithin(left,prose));
          }else glideWithin(left,prose);
        });
      });
    });
  }
  function focusPdf(anchor){
    const page=document.querySelector('.pdfpage[data-page="'+anchor.page+'"]');
    const hits=highlightGroups[anchor.id]||[];
    if(!page||!hits.length)return;
    const first=hits.reduce((best,hit)=>hit.offsetTop<best.offsetTop?hit:best,hits[0]);
    glideWithin(right,first);
  }

  hydrateHighlights();
  proseLinks.forEach(link=>{
    const activate=()=>{
      const anchor=byId[link.dataset.anchor];
      if(!anchor)return;
      selectPdf(anchor.id);
      history.replaceState(null,'',link.getAttribute('href'));
      if(isMobile()){
        showMobilePane('pdf',true,false);
        requestAnimationFrame(()=>focusPdf(anchor));
      }else focusPdf(anchor);
    };
    link.addEventListener('click',event=>{event.preventDefault();activate();});
    link.addEventListener('mouseenter',()=>{hoveredId=link.dataset.anchor;renderHighlightState();});
    link.addEventListener('mouseleave',()=>{if(hoveredId===link.dataset.anchor){hoveredId='';renderHighlightState();}});
    link.addEventListener('focus',()=>{hoveredId=link.dataset.anchor;renderHighlightState();});
    link.addEventListener('blur',()=>{if(hoveredId===link.dataset.anchor){hoveredId='';renderHighlightState();}});
  });
  mediaJumps.forEach(link=>{
    link.addEventListener('click',event=>{
      const anchor=byId[link.dataset.anchor];
      if(!anchor)return;
      event.preventDefault();
      selectPdf(anchor.id);
      history.replaceState(null,'',link.getAttribute('href'));
      if(isMobile()){
        showMobilePane('pdf',true,false);
        requestAnimationFrame(()=>focusPdf(anchor));
      }else focusPdf(anchor);
    });
  });

  ['pointerdown','touchstart'].forEach(eventName=>{
    left.addEventListener(eventName,cancelGlide,{passive:true});
    right.addEventListener(eventName,cancelGlide,{passive:true});
  });
  left.addEventListener('wheel',cancelGlide,{passive:true});
  mobileTabs.forEach(tab=>tab.addEventListener('click',event=>{event.preventDefault();showMobilePane(tab.dataset.mobileView);}));
  document.addEventListener('click',event=>{
    if(event.target.closest('.a,.hl,.media-jump'))return;
    clearSelection();
  });

  layout.addEventListener('scroll',()=>{
    if(!isMobile())return;
    cancelAnimationFrame(mobileFrame);
    mobileFrame=requestAnimationFrame(()=>{
      const pane=Math.round(layout.scrollLeft/layout.clientWidth)===1?'pdf':'article';
      if(layout.dataset.mobilePane!==pane)setMobileState(pane);
    });
  },{passive:true});
  window.addEventListener('resize',()=>{
    if(!isMobile())return;
    const pane=layout.dataset.mobilePane||'article';
    requestAnimationFrame(()=>showMobilePane(pane,false));
  });

  function setSplit(clientX){
    const bounds=layout.getBoundingClientRect();
    const percent=Math.max(36,Math.min(68,((clientX-bounds.left)/bounds.width)*100));
    document.documentElement.style.setProperty('--left-pane',percent+'%');
  }
  splitter.addEventListener('pointerdown',event=>{event.preventDefault();splitter.classList.add('is-dragging');splitter.setPointerCapture(event.pointerId);setSplit(event.clientX);});
  splitter.addEventListener('pointermove',event=>{if(splitter.hasPointerCapture(event.pointerId))setSplit(event.clientX);});
  splitter.addEventListener('pointerup',event=>{splitter.classList.remove('is-dragging');if(splitter.hasPointerCapture(event.pointerId))splitter.releasePointerCapture(event.pointerId);});
  splitter.addEventListener('keydown',event=>{
    if(event.key!=='ArrowLeft'&&event.key!=='ArrowRight')return;
    event.preventDefault();
    const current=parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--left-pane'))||52;
    const next=Math.max(36,Math.min(68,current+(event.key==='ArrowRight'?2:-2)));
    document.documentElement.style.setProperty('--left-pane',next+'%');
  });

  function applyZoom(nextZoom,clientX,clientY){
    const oldWidth=pages.scrollWidth;
    const oldHeight=pages.scrollHeight;
    const bounds=right.getBoundingClientRect();
    const localX=clientX-bounds.left;
    const localY=clientY-bounds.top;
    const ratioX=oldWidth?((right.scrollLeft+localX)/oldWidth):0;
    const ratioY=oldHeight?((right.scrollTop+localY)/oldHeight):0;
    zoom=Math.max(1,Math.min(3,nextZoom));
    pages.style.width=(zoom*100)+'%';
    requestAnimationFrame(()=>{right.scrollLeft=ratioX*pages.scrollWidth-localX;right.scrollTop=ratioY*pages.scrollHeight-localY;});
  }
  right.addEventListener('wheel',event=>{
    cancelGlide();
    if(!(event.ctrlKey||event.metaKey))return;
    event.preventDefault();
    applyZoom(zoom*Math.exp(-event.deltaY*.008),event.clientX,event.clientY);
  },{passive:false});
  let gestureStartZoom=1;
  right.addEventListener('gesturestart',event=>{event.preventDefault();gestureStartZoom=zoom;},{passive:false});
  right.addEventListener('gesturechange',event=>{event.preventDefault();applyZoom(gestureStartZoom*event.scale,event.clientX,event.clientY);},{passive:false});
  window.addEventListener('keydown',event=>{
    if(event.key==='Escape')clearSelection();
    if(event.target.matches('input,textarea,select,button,[contenteditable]'))return;
    const index=Math.max(0,proseLinks.findIndex(link=>link.dataset.anchor===(pinnedId||selectedId)));
    if(event.key==='j'||event.key==='ArrowDown'){event.preventDefault();proseLinks[Math.min(proseLinks.length-1,index+1)]?.click();}
    if(event.key==='k'||event.key==='ArrowUp'){event.preventDefault();proseLinks[Math.max(0,index-1)]?.click();}
  });

  const target=location.hash?document.querySelector(location.hash):null;
  if(isMobile()){
    if(target?.classList.contains('hl')){
      showMobilePane('pdf',false,false);
      selectPdf(target.dataset.anchor||'');
      requestAnimationFrame(()=>glideWithin(right,target));
    }else if(target?.classList.contains('a')){
      showMobilePane('article',false,false);
      pinnedId=target.dataset.anchor||'';
      selectPdf(pinnedId);
      requestAnimationFrame(()=>glideWithin(left,target));
    }else if(location.hash==='#pdf-pane')showMobilePane('pdf',false,false);
    else showMobilePane('article',false,false);
  }
})();
