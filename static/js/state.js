const STATE = {
  view: 'inbox',
  project: '项目 1',
  projectId: null,
  region: 'China',
  regionId: null,
  regionLabel: '',
  group: null,
  groupId: null,
  file: null,
  fileId: null,
  projectList: [],
  regions: [],
  groups: []
};
const PERM = { role: 'approver' };
const DATA = { acceptance: [] };

function canEdit(){
  return ['editor','approver','admin'].includes(PERM.role);
}
function canApprove(){
  return ['approver','admin'].includes(PERM.role);
}
