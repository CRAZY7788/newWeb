const STATE = {
  view: 'inbox',
  library: 'product',
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
  traceReturnView: 'files',
  projectList: [],
  regions: [],
  folders: [],
  groups: []
};
const PERM = { role: 'viewer', userId: null, username: '' };
const DATA = { acceptance: [] };

function canEdit(){
  return ['editor','approver','admin'].includes(PERM.role);
}
function canApprove(){
  return ['approver','admin'].includes(PERM.role);
}
