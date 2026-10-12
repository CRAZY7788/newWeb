const themeBtn=$('#themeBtn');
const root=document.documentElement;
const savedTheme=localStorage.getItem('theme');
if(savedTheme==='dark'){ root.classList.add('dark'); }
themeBtn.addEventListener('click', ()=>{
  root.classList.toggle('dark');
  localStorage.setItem('theme', root.classList.contains('dark') ? 'dark':'light');
});

async function loadMe(){
  const j = await fetch('/api/me', {credentials:'same-origin'}).then(r=>r.json());
  if(j.ok && j.user){
    $('#who').textContent = j.user.username;
    PERM.role = j.user.role || 'viewer';
    const sel = $('#roleSelect');
    sel.value = PERM.role;
    sel.disabled = true;
    sel.title = '角色由账号决定';
  } else {
    location.href = '/login';
  }
}
