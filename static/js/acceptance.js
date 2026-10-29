const acceptList=$('#acceptList'), inboxBadge=$('#inboxBadge');
const ctxModal=$('#ctxModal'), ctxMenu=$('#ctxMenu');
const formDialog=$('#formDialog'), dialogTitle=$('#dialogTitle'), dialogForm=$('#dialogForm'), roleField=$('#roleField'), reasonField=$('#reasonField'), authFields=$('#authFields');

async function loadAcceptance(){
  try{
    const json = await api('/api/acceptance');
    DATA.acceptance = json.items.map(t=>({
      id: t.id,
      file_id: t.file_id,
      name: t.name,
      url: '/versions/download?file_id='+t.file_id,
      date: t.date,
      owner: t.owner,
      status: t.status || '待验收'
    }));
  }catch(e){
    DATA.acceptance = [];
    toast(e.message);
  }
  refreshAcceptList();
}

function refreshAcceptList(){
  acceptList.innerHTML='';
  DATA.acceptance.forEach((d,idx)=>{
    const row=document.createElement('div');
    row.className='row';
    row.dataset.id=d.id;
    row.dataset.fileId=d.file_id;
    row.dataset.url=d.url;
    row.innerHTML = `<span class="idx">${idx+1}.</span><span>${d.name}</span><span class="tag">${d.status}</span><span>${d.date}</span><span>${d.owner||''}</span>`;
    row.ondblclick = ()=>{
      window.open(d.url);
      toast('打开：'+d.name);
    };
    row.addEventListener('contextmenu', (e)=> openAcceptMenu(e,row));
    addLongPress(row, (e)=> openAcceptMenu(e,row));
    acceptList.appendChild(row);
  });
  inboxBadge.textContent = DATA.acceptance.length;
}

function openAcceptMenu(e,row){
  e.preventDefault();
  if(!canApprove()){
    toast('当前角色不能验收');
    return;
  }
  const items=[
    {text:'验收', action:()=> openDialog('approve', row)},
    {text:'拒绝', action:()=> openDialog('reject', row)}
  ];
  openContextMenu(e, items);
}

function openContextMenu(e, items){
  ctxMenu.innerHTML='';
  items.forEach(it=>{
    const b=document.createElement('button');
    b.textContent=it.text;
    b.onclick=()=>{ closeContextMenu(); it.action(); };
    ctxMenu.appendChild(b);
  });
  ctxModal.classList.add('open');
  ctxMenu.style.position='absolute';
  ctxMenu.style.left=e.clientX+'px';
  ctxMenu.style.top=e.clientY+'px';
}
function closeContextMenu(){ ctxModal.classList.remove('open'); }
ctxModal.addEventListener('click', (e)=>{ if(e.target===ctxModal) closeContextMenu(); });

$('#cancelDialog').addEventListener('click', ()=> formDialog.classList.remove('open'));
function openDialog(type,row){
  if(type==='approve'){
    dialogTitle.textContent='验收';
    roleField.hidden=false;
    reasonField.hidden=true;
    authFields.hidden=true;
    roleField.querySelector('input').required = false;
  } else {
    dialogTitle.textContent='拒绝';
    roleField.hidden=true;
    reasonField.hidden=false;
    authFields.hidden=true;
  }
  dialogForm.querySelectorAll('input,textarea').forEach(el => { el.required = false; });
  if(type==='reject'){
    reasonField.querySelector('textarea').required = false;
  }
  dialogForm.reset();
  formDialog.classList.add('open');
  dialogForm.onsubmit = async (e)=>{
    e.preventDefault();
    const id = Number(row.dataset.id);
    const fd = new FormData(dialogForm);
    try{
      if(type==='approve'){
        await api('/api/acceptance/approve', {
          method:'POST',
          body: JSON.stringify({task_id:id, role: fd.get('role')||''})
        });
      }else{
        await api('/api/acceptance/reject', {
          method:'POST',
          body: JSON.stringify({task_id:id, reason: fd.get('reason')||''})
        });
      }
      formDialog.classList.remove('open');
      await loadAcceptance();
      toast(type==='approve' ? '已验收' : '已拒绝');
    }catch(err){
      toast(err.message);
    }
  };
}
