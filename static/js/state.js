const STATE = {
  view: 'inbox',
  project: '项目 1',
  projectId: null,
  region: 'China',
  regionId: null,
  regionLabel: '',
  currentFolderId: null,
  folderStack: [],
  group: null,
  groupId: null,
  file: null,
  fileId: null,
  projectList: [],
  regions: [],
  folders: [],
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
