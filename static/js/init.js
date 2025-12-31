parseHash();
routeToState();
loadAcceptance();

// backs
$$('.back .btn').forEach(btn=> btn.addEventListener('click', ()=> {
  show(btn.dataset.back);
  if(btn.dataset.back==='detail') STATE.file=null;
  if(btn.dataset.back==='files') STATE.file=null;
}));
