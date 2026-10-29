async function boot(){
  parseHash();
  try{
    await loadMe();
    await loadProjects();
    await loadAcceptance();
    await routeToState();
  }catch(err){
    toast(err.message);
  }

  $$('.back .btn').forEach(btn=> btn.addEventListener('click', async ()=>{
    const back = btn.dataset.back;
    STATE.file = null;
    STATE.fileId = null;
    if(back==='board'){
      resetFolderNav();
      STATE.group = null;
      STATE.groupId = null;
    }
    if(back==='detail'){
      STATE.group = null;
      STATE.groupId = null;
    }
    try{
      if(back==='board') await loadBoard(STATE.projectId);
      if(back==='detail') await populateDetail(STATE.regionId, STATE.region, STATE.regionLabel);
      if(back==='files' && STATE.groupId) await openFiles(STATE.groupId, STATE.group);
      show(back);
    }catch(err){
      toast(err.message);
    }
  }));
}

boot();
