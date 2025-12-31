function syncHash(){
  const p=new URLSearchParams();
  p.set('view',STATE.view);
  if(STATE.project) p.set('project',STATE.project);
  if(STATE.region) p.set('region',STATE.region);
  if(STATE.group) p.set('group',STATE.group);
  if(STATE.file) p.set('file',STATE.file);
  location.hash = p.toString();
}

function parseHash(){
  const p = new URLSearchParams(location.hash.replace(/^#/,''));
  STATE.view = p.get('view') || STATE.view;
  STATE.project = p.get('project') || STATE.project;
  STATE.region = p.get('region') || STATE.region;
  STATE.group = p.get('group') || STATE.group;
  STATE.file = p.get('file') || STATE.file;
}

window.addEventListener('hashchange', ()=>{ parseHash(); routeToState(); });

function routeToState(){
  $$('.sidebar .nav-item').forEach(n=>n.classList.remove('active'));
  if(STATE.view==='inbox') $('.sidebar .nav-item[data-type="inbox"]').classList.add('active');
  if(STATE.view!=='inbox'){ $(`.sidebar .nav-item[data-type="project"][data-project="${STATE.project}"]`)?.classList.add('active'); }
  $('#boardTitle').textContent=STATE.project;
  $('#detailProject').textContent=STATE.project;
  $('#fileProject').textContent=STATE.project;
  $('#verProject').textContent=STATE.project;

  if(STATE.view==='inbox'){ show('inbox'); }
  else if(STATE.view==='board'){ show('board'); }
  else if(STATE.view==='detail'){ populateDetail(STATE.region); show('detail'); }
  else if(STATE.view==='files'){ populateDetail(STATE.region); openFiles(STATE.group||'占位条目 1'); }
  else if(STATE.view==='versions'){ populateDetail(STATE.region); openFiles(STATE.group||'占位条目 1'); openVersionsFromRow({dataset:{file: STATE.file||'文件 A'}}); }
}
