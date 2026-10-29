function syncHash(){
  const p=new URLSearchParams();
  p.set('view', STATE.view);
  if(STATE.project) p.set('project', STATE.project);
  if(STATE.projectId) p.set('pid', STATE.projectId);
  if(STATE.region) p.set('region', STATE.region);
  if(STATE.regionId) p.set('rid', STATE.regionId);
  if(STATE.currentFolderId != null) p.set('cfid', STATE.currentFolderId);
  if(STATE.group) p.set('group', STATE.group);
  if(STATE.groupId) p.set('gid', STATE.groupId);
  if(STATE.file) p.set('file', STATE.file);
  if(STATE.fileId) p.set('fid', STATE.fileId);
  location.hash = p.toString();
}

function parseHash(){
  const p = new URLSearchParams(location.hash.replace(/^#/,''));
  STATE.view = p.get('view') || STATE.view;
  STATE.project = p.get('project') || STATE.project;
  STATE.projectId = p.get('pid') ? Number(p.get('pid')) : STATE.projectId;
  STATE.region = p.get('region') || STATE.region;
  STATE.regionId = p.get('rid') ? Number(p.get('rid')) : STATE.regionId;
  if(p.has('cfid')){
    STATE.currentFolderId = Number(p.get('cfid'));
  } else if(STATE.view === 'detail'){
    STATE.currentFolderId = null;
  }
  STATE.group = p.get('group') || STATE.group;
  STATE.groupId = p.get('gid') ? Number(p.get('gid')) : STATE.groupId;
  STATE.file = p.get('file') || STATE.file;
  STATE.fileId = p.get('fid') ? Number(p.get('fid')) : STATE.fileId;
}

window.addEventListener('hashchange', ()=>{ parseHash(); routeToState(); });

function resolveProject(){
  const list = STATE.projectList || [];
  const p = list.find(x=>x.id===STATE.projectId) || list.find(x=>x.name===STATE.project) || list[0];
  if(p){
    STATE.projectId = p.id;
    STATE.project = p.name;
  }
}

async function routeToState(){
  $$('.sidebar .nav-item').forEach(n=>n.classList.remove('active'));
  if(STATE.view==='inbox'){
    $('.sidebar .nav-item[data-type="inbox"]')?.classList.add('active');
  } else if(STATE.view==='qms'){
    $('.sidebar .nav-item[data-type="qms"]')?.classList.add('active');
  } else if(STATE.view==='templates'){
    $('.sidebar .nav-item[data-type="templates"]')?.classList.add('active');
  } else if(['board','detail','files','versions','trace'].includes(STATE.view)){
    $(`.sidebar .nav-item[data-type="project"][data-project-id="${STATE.projectId}"]`)?.classList.add('active');
  }
  $('#boardTitle').textContent = STATE.project || '';
  $('#detailProject') && ($('#detailProject').textContent = STATE.project || '');
  $('#fileProject').textContent = STATE.project || '';
  $('#verProject').textContent = STATE.project || '';

  try{
    if(STATE.view==='inbox'){
      show('inbox');
    } else if(STATE.view==='qms'){
      show('qms');
    } else if(STATE.view==='templates'){
      await loadTemplateCatalog();
      show('templates');
    } else {
      resolveProject();
      await loadBoard(STATE.projectId);
      if(STATE.view==='board'){
        show('board');
      } else if(STATE.view==='detail'){
        await populateDetail(STATE.regionId, STATE.region, STATE.regionLabel);
        show('detail');
      } else if(STATE.view==='files'){
        await populateDetail(STATE.regionId, STATE.region, STATE.regionLabel);
        if(STATE.groupId) await openFiles(STATE.groupId, STATE.group);
        else show('detail');
      } else if(STATE.view==='versions'){
        await populateDetail(STATE.regionId, STATE.region, STATE.regionLabel);
        if(STATE.groupId) await openFiles(STATE.groupId, STATE.group, {silent:true});
        if(STATE.fileId){
          $('#verFile').textContent = STATE.file || '';
          await populateVersions(STATE.fileId, STATE.file);
          show('versions');
        }
      } else if(STATE.view==='trace'){
        await populateDetail(STATE.regionId, STATE.region, STATE.regionLabel);
        if(STATE.groupId) await openFiles(STATE.groupId, STATE.group, {silent:true});
        if(STATE.fileId) await openTrace(STATE.fileId, STATE.file);
      }
    }
  }catch(err){
    toast(err.message);
  }
}
