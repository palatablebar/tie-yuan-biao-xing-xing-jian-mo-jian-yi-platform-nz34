/**
 * 品牌、导航、角色权限与共享枚举（前端唯一定义处）。
 * 后端对应：backend/src/constants/{roles,enums}.py；README 列出全部出现位置。
 */
export const BRAND = {
  short: 'starmodel',
  title: '贴源表星型建模建议台',
  org: '禾丰零售 · 数仓组',
  edition: 'DRAFTING DESK · 2026',
  subtitle: '把 24 张贴源表摊在制图纸上：先看清唯一率与包含度，再决定谁是事实、谁是维度。',
  loginLead: '星型模型不是画出来的，是量出来的：主键候选、包含度、粒度去重计数，每一步都留在后端账本上。',
  loginPoints: [
    ['剖', '24 张贴源表逐列剖析唯一率、空值率、基数与样本值。'],
    ['连', '同名键 + 包含度 ≥ 0.98 + 右侧唯一 → 主外键候选，共 18 条边。'],
    ['定', '按字段模式与体量判定事实/维度，输出粒度、关联与 CREATE TABLE DDL。'],
  ],
};

export const NAV = [
  { to: '#/overview', no: '00', label: '制图台总览', permission: 'overview:read' },
  { to: '#/tables', no: '01', label: '贴源表与剖析', permission: 'table:read' },
  { to: '#/relations', no: '02', label: '关系图', permission: 'relation:read' },
  { to: '#/suggestions', no: '03', label: '建模建议', permission: 'suggestion:read' },
  { to: '#/audit', no: '04', label: '审计日志', permission: 'audit:read' },
];

export const ROLE_LABELS = {
  admin: '平台管理员',
  analyst: '建模专员',
  viewer: '只读访客',
};

export const PERMISSIONS = {
  admin: [
    'overview:read', 'table:read', 'table:write', 'profile:read', 'relation:read',
    'run:read', 'run:create', 'suggestion:read', 'suggestion:adopt', 'suggestion:review',
    'export:read', 'audit:read',
  ],
  analyst: [
    'overview:read', 'table:read', 'profile:read', 'relation:read',
    'run:read', 'run:create', 'suggestion:read', 'suggestion:review', 'export:read',
  ],
  viewer: ['overview:read', 'table:read', 'profile:read', 'relation:read', 'run:read', 'suggestion:read'],
};

export const ENUMS = {
  role: { admin: '平台管理员', analyst: '建模专员', viewer: '只读访客' },
  domain: {
    sales: '销售',
    inventory: '库存',
    member: '会员',
    product: '商品',
    supply: '供应',
    org: '组织',
    log: '日志',
    config: '配置',
  },
  dtype: { int: '整数', decimal: '数值', date: '日期', string: '文本', bool: '布尔' },
  relationKind: { 'pk-fk': '主外键', fk: '弱外键候选' },
  suggestionRole: { fact: '事实表', dim: '维度表' },
  suggestionStatus: { pending: '待采纳', adopted: '已采纳', dismissed: '已驳回' },
  runStatus: { queued: '排队中', running: '剖析中', success: '成功', partial: '部分成功', failed: '失败' },
  trigger: { manual: '手动', schedule: '定时', seed: '初始化' },
};

export function can(role, permission) {
  return (PERMISSIONS[role] || []).includes(permission);
}

export function roleTone(role) {
  return { fact: 'fact', dim: 'dim' }[role] || 'info';
}

export function statusTone(status) {
  return { pending: 'pending warn', adopted: 'adopted ok', dismissed: 'dismissed danger' }[status] || 'info';
}

export function runTone(status) {
  return { success: 'ok', partial: 'warn', failed: 'danger', running: 'info' }[status] || 'info';
}
