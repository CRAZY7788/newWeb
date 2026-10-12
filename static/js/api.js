async function parseApiResponse(res){
  let json = null;
  try { json = await res.json(); } catch(e) { json = null; }
  if(res.status === 401){
    location.href = '/login';
    throw new Error((json && json.error) || '未登录');
  }
  if(!json || json.ok === false){
    throw new Error((json && json.error) || ('请求失败 ' + res.status));
  }
  return json;
}

async function api(url, opts={}){
  const res = await fetch(url, {
    credentials: 'same-origin',
    headers: {'Content-Type':'application/json', ...(opts.headers||{})},
    ...opts
  });
  return parseApiResponse(res);
}

async function apiForm(url, formData){
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    body: formData
  });
  return parseApiResponse(res);
}
