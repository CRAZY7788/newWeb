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

// 视图控制
const views = {
  inbox: $('#acceptanceView'),
  board: $('#boardView'),
  detail: $('#detailView'),
  files: $('#fileView'),
  versions: $('#versionView')
};
function show(id){
  Object.values(views).forEach(v=>v.hidden=true);
  views[id].hidden=false;
  STATE.view=id;
  syncHash();
}
