<script>
fetch("/static/acceptance-data.json")
  .then(res => res.json())
  .then(data => {
    renderPendingFiles(data.pending_files);
  });

function showHistory(fileId) {
  fetch("/static/acceptance-data.json")
    .then(res => res.json())
    .then(data => {
      const history = data.history_versions[fileId] || [];
      renderHistory(history);
    });
}
function populateVersions(fileName){
  const scroller = document.getElementById('versionScroller');
  scroller.innerHTML = '';
  ['V1','V2','V2.1','V2.2','V3'].forEach((v,i)=>{
    const card = document.createElement('article');
    card.className = 'version-card';
    card.innerHTML = `
      <h3>${v}</h3>
      <p style="color:var(--muted)">${fileName} 的历史版本</p>
      <p class="meta"><span>${new Date(2024+i, i%12, 10+i).toLocaleDateString()}</span><span>by User${i+1}</span></p>
      <div class="actions">
        <button class="btn ok">回滚</button>
        <button class="btn">对比</button>
      </div>`;
    // ✅ 双击打开受控下载路由（不再 404）
    card.ondblclick = () => {
      const url = `/versions/download?file=${encodeURIComponent(fileName)}&v=${encodeURIComponent(v)}`;
      window.open(url, '_blank');
    };
    scroller.appendChild(card);
  });
}

</script>
