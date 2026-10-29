const templateListEl = $('#templateList');

async function loadTemplateCatalog(){
  if(!templateListEl) return;
  templateListEl.innerHTML = '<p class="muted">加载中…</p>';
  try{
    const res = await fetch('/static/template-catalog.json', {cache:'no-store'});
    const items = await res.json();
    templateListEl.innerHTML = '';
    items.forEach((t, idx)=>{
      const row = document.createElement('div');
      row.className = 'row';
      row.innerHTML = `<span class="idx">${idx + 1}.</span><span><b>${t.category}</b> · ${t.name}</span><span class="tag">只读</span><span class="muted">${t.description || ''}</span><span></span>`;
      row.ondblclick = ()=>{
        window.open('/static/versions/history.pdf');
        toast('打开示例文件（日后替换为真实模板）');
      };
      templateListEl.appendChild(row);
    });
  }catch(e){
    templateListEl.innerHTML = '<p class="muted">暂无模板目录</p>';
  }
}
