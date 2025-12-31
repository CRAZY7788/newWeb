const sidebar=$('#sidebar'), overlay=$('#overlay'), toggleSidebar=$('#toggleSidebar');

function openSidebar(){ sidebar.classList.add('open'); overlay.classList.add('open'); }
function closeSidebar(){ sidebar.classList.remove('open'); overlay.classList.remove('open'); }

toggleSidebar.addEventListener('click', ()=> sidebar.classList.contains('open') ? closeSidebar() : openSidebar());
overlay.addEventListener('click', closeSidebar);

// search filter
$('#searchInput').addEventListener('input', e=>{
  const q = e.target.value.trim().toLowerCase();
  $$('.sidebar .nav-item[data-type="project"]').forEach(n => n.style.display = (n.dataset.project.toLowerCase().includes(q) || q==='') ? '' : 'none');
});

// sidebar nav
const boardTitle=$('#boardTitle');
$('.sidebar').addEventListener('click', e=>{
  const item=e.target.closest('.nav-item'); if(!item) return;
  $$('.nav-item').forEach(n=>n.classList.remove('active'));
  item.classList.add('active');
  const type=item.dataset.type;
  if(type==='project'){
    const name=item.dataset.project; STATE.project=name;
    boardTitle.textContent=name;
    $('#detailProject').textContent=name;
    $('#fileProject').textContent=name;
    $('#verProject').textContent=name;
    show('board'); closeSidebar();
  }else if(type==='inbox'){ show('inbox'); closeSidebar(); }
  else if(type==='template'){ boardTitle.textContent='模板库（占位）'; show('board'); closeSidebar(); }
});
