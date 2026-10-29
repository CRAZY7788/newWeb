const $ = (s, c=document)=>c.querySelector(s);
const $$ = (s, c=document)=>Array.from(c.querySelectorAll(s));

function toast(text, type='ok', timeout=1800){
  const el = document.createElement('div');
  el.className='toast';
  el.textContent=text;
  $('#toasts').appendChild(el);
  setTimeout(()=>{ el.style.opacity=0; setTimeout(()=>el.remove(),300); }, timeout);
}

function addLongPress(el, cb){
  let t;
  el.addEventListener('touchstart', e => { t=setTimeout(()=>cb(e.changedTouches[0]),500); }, {passive:true});
  el.addEventListener('touchend', ()=>clearTimeout(t), {passive:true});
  el.addEventListener('touchmove', ()=>clearTimeout(t), {passive:true});
}

const views = {
  inbox: $('#acceptanceView'),
  board: $('#boardView'),
  detail: $('#detailView'),
  files: $('#fileView'),
  versions: $('#versionView'),
  trace: $('#traceView'),
  qms: $('#qmsView'),
  templates: $('#templatesView')
};
function show(id){
  Object.values(views).forEach(v=>{ if(v) v.hidden=true; });
  if(!views[id]) return;
  views[id].hidden=false;
  STATE.view=id;
  syncHash();
}
