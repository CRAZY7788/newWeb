const acceptList=$('#acceptList'), inboxBadge=$('#inboxBadge');
const ctxModal=$('#ctxModal'), ctxMenu=$('#ctxMenu');
const formDialog=$('#formDialog'), dialogTitle=$('#dialogTitle'), dialogForm=$('#dialogForm'), roleField=$('#roleField'), reasonField=$('#reasonField'), authFields=$('#authFields');

async function loadAcceptance(){
  try{
    const res = await fetch('/static/acceptance-data.json', {cache:'no-store'});
    const json = await res.json();
    DATA.acceptance = json;
  }catch(e){
    DATA.acceptance = Array.from({length:6}).map((_,i)=>({
      id:'ACC-'+(1000+i),
      name:`提交文档_${i+1}.pdf`,
      url:`/static/submission_${i+1}.pdf`,
      date:new Date().toLocaleDateString(),
      owner:'user'+(i+1),
      status:'待验收'
    }));
  }
  refreshAcceptList();
}

function refreshAcceptList(){
  acceptList.innerHTML='';
  DATA.acceptance.forEach((d,idx)=>{
    const row=document.createElement('div'); row.className='row'; row.dataset.id=d.id; row.dataset.url=d.url;
    row.innerHTML = `<span class="idx">${idx+1}.</span><span>${d.name}</span><span class="tag">${d.status}</span><span>${d.date}</span><span>${d.owner}</span>`;
    row.ondblclick = ()=>{
      const a=document.createElement('a'); a.href=d.url; a.target='_blank'; a.download=d.name; document.body.appendChild(a); a.click(); a.remove();
      toast('开始下载/打开：'+d.name);
    };
    row.addEventListener('contextmenu', (e)=> openAcceptMenu(e,row));
    addLongPress(row, (e)=> openAcceptMenu(e,row));
    acceptList.appendChild(row);
  });
  inboxBadge.textContent = DATA.acceptance.length;
}

function openAcceptMenu(e,row){
  e.preventDefault();
  const items=[
    {text:'验收', action:()=> openDialog('approve', row)},
    {text:'拒绝', action:()=> openDialog('reject', row)}
  ];
  openContextMenu(e, items);
}

// context menu
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

// dialog
$('#cancelDialog').addEventListener('click', ()=> formDialog.classList.remove('open'));
function openDialog(type,row){
  if(type==='approve'){ dialogTitle.textContent='验收'; roleField.hidden=false; reasonField.hidden=true; authFields.hidden=false; }
  else { dialogTitle.textContent='拒绝'; roleField.hidden=true; reasonField.hidden=false; authFields.hidden=false; }
  dialogForm.reset();
  formDialog.classList.add('open');
  dialogForm.onsubmit = (e)=>{
    e.preventDefault();
    const id=row.dataset.id;
    const idx=DATA.acceptance.findIndex(x=>x.id===id);
    if(idx>-1){ DATA.acceptance.splice(idx,1); }
    formDialog.classList.remove('open');
    refreshAcceptList();
    toast((type==='approve'?'已验收：':'已拒绝：')+id);
  };
}
