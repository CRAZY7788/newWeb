const themeBtn=$('#themeBtn');
const root=document.documentElement;
const savedTheme=localStorage.getItem('theme');
if(savedTheme==='dark'){ root.classList.add('dark'); }
themeBtn.addEventListener('click', ()=>{
  root.classList.toggle('dark');
  localStorage.setItem('theme', root.classList.contains('dark') ? 'dark':'light');
});

// 获取用户名
fetch('/api/me').then(r=>r.json()).then(j=>{
  if(j.ok && j.user){ $('#who').textContent=j.user.username; }
});
