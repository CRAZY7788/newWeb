const sidebar=$('#sidebar'), overlay=$('#overlay'), toggleSidebar=$('#toggleSidebar');

function openSidebar(){ sidebar.classList.add('open'); overlay.classList.add('open'); }
function closeSidebar(){ sidebar.classList.remove('open'); overlay.classList.remove('open'); }

toggleSidebar.addEventListener('click', ()=> sidebar.classList.contains('open') ? closeSidebar() : openSidebar());
overlay.addEventListener('click', closeSidebar);

$('#searchInput').addEventListener('input', e=>{
  const q = e.target.value.trim().toLowerCase();
  $$('#projectNav .nav-item').forEach(n => {
    n.style.display = (n.dataset.project.toLowerCase().includes(q) || q==='') ? '' : 'none';
  });
});

async function loadProjects(){
  const json = await api('/api/projects');
  STATE.projectList = json.projects;
  const nav = $('#projectNav');
  nav.innerHTML = '';
  json.projects.forEach(p=>{
    const el = document.createElement('div');
    el.className = 'nav-item';
    el.dataset.type = 'project';
    el.dataset.project = p.name;
    el.dataset.projectId = p.id;
    el.textContent = p.name;
    nav.appendChild(el);
  });
  if(!STATE.projectId && json.projects.length){
    const match = json.projects.find(p=>p.name===STATE.project) || json.projects[0];
    STATE.projectId = match.id;
    STATE.project = match.name;
  }
}

$('.sidebar').addEventListener('click', async e=>{
  const item=e.target.closest('.nav-item'); if(!item) return;
  $$('.nav-item').forEach(n=>n.classList.remove('active'));
  item.classList.add('active');
  const type=item.dataset.type;
  try{
    if(type==='project'){
      STATE.project = item.dataset.project;
      STATE.projectId = Number(item.dataset.projectId);
      STATE.region = null;
      STATE.regionId = null;
      STATE.group = null;
      STATE.groupId = null;
      STATE.file = null;
      STATE.fileId = null;
      $('#boardTitle').textContent = STATE.project;
      $('#detailProject').textContent = STATE.project;
      $('#fileProject').textContent = STATE.project;
      $('#verProject').textContent = STATE.project;
      await loadBoard(STATE.projectId);
      show('board');
      closeSidebar();
    }else if(type==='inbox'){
      await loadAcceptance();
      show('inbox');
      closeSidebar();
    }else if(type==='qms'){
      show('qms');
      closeSidebar();
    }else if(type==='templates'){
      await loadTemplateCatalog();
      show('templates');
      closeSidebar();
    }
  }catch(err){
    toast(err.message);
  }
});
