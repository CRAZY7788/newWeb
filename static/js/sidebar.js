const sidebar=$('#sidebar'), overlay=$('#overlay'), toggleSidebar=$('#toggleSidebar');

function openSidebar(){ sidebar.classList.add('open'); overlay.classList.add('open'); }
function closeSidebar(){ sidebar.classList.remove('open'); overlay.classList.remove('open'); }

toggleSidebar.addEventListener('click', ()=> sidebar.classList.contains('open') ? closeSidebar() : openSidebar());
overlay.addEventListener('click', closeSidebar);

async function loadProjects(){
  const json = await api('/api/projects?kind=product');
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
      STATE.library = 'product';
      STATE.project = item.dataset.project;
      STATE.projectId = Number(item.dataset.projectId);
      STATE.regionId = null;
      STATE.group = null;
      STATE.groupId = null;
      STATE.file = null;
      STATE.fileId = null;
      resetFolderNav();
      syncProjectLabels();
      syncLibraryChrome();
      await loadBoard(STATE.projectId);
      show('board');
      closeSidebar();
    }else if(type==='inbox'){
      await loadAcceptance();
      show('inbox');
      closeSidebar();
    }else if(type==='qms'){
      await openQmsLibrary();
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
