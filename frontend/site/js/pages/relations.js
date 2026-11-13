import { api } from '../api.js';
import { ENUMS, can, versionTone } from '../config.js';
import { confidenceBar, drawer, errorBox, errorMessage, esc, field, fmtRatio, kv, table, toast } from '../ui.js';

const state = { kind: '', scope: '' };
const NODE_W = 148;
const NODE_H = 46;
const VIEW = { w: 980, h: 470 };

function groupNodes(data) {
  const factIds = data.nodes.filter((node) => node.role === 'fact').map((node) => node.id);
  const factSet = new Set(factIds);
  const primarySet = new Set(
    data.edges.filter((edge) => factSet.has(edge.left_table_id)).map((edge) => edge.right_table_id),
  );
  const dims = data.nodes.filter((node) => node.role === 'dim');
  return {
    facts: data.nodes.filter((node) => factSet.has(node.id)),
    primary: dims.filter((node) => primarySet.has(node.id)),
    secondary: dims.filter((node) => !primarySet.has(node.id)),
    unrelated: data.nodes.filter((node) => node.role === 'none' || node.degree === 0),
  };
}

function place(nodes, x) {
  const top = 40;
  const bottom = VIEW.h - 40;
  return nodes.map((node, index) => ({
    ...node,
    x,
    y: nodes.length === 1 ? VIEW.h / 2 : top + (index * (bottom - top)) / (nodes.length - 1),
  }));
}

function edgePath(a, b) {
  const dx = Math.max(56, Math.abs(b.x - a.x) * 0.48);
  const c1 = a.x + (b.x >= a.x ? dx : -dx);
  const c2 = b.x + (b.x >= a.x ? -dx : dx);
  return `M ${a.x} ${a.y} C ${c1} ${a.y}, ${c2} ${b.y}, ${b.x} ${b.y}`;
}

function nodeMarkup(node, group) {
  const cls = ['node', node.role, group === 'secondary' ? 'secondary' : ''].filter(Boolean).join(' ');
  return `<g class="${cls}" data-node="${node.id}" transform="translate(${node.x} ${node.y})">
    <title>${esc(node.name)} · ${esc(node.cn_name)} · ${node.degree} 条关系</title>
    <rect class="plate" x="${-NODE_W / 2}" y="${-NODE_H / 2}" width="${NODE_W}" height="${NODE_H}" rx="2" />
    <text class="cn" text-anchor="middle" y="-3">${esc(node.cn_name)}</text>
    <text class="name" text-anchor="middle" y="13">${esc(node.name)}</text>
  </g>`;
}

function renderSvg(data, groups, positions) {
  const byId = new Map(positions.map((node) => [node.id, node]));
  const edges = data.edges
    .map((edge) => {
      const from = byId.get(edge.left_table_id);
      const to = byId.get(edge.right_table_id);
      if (!from || !to) return '';
      return `<path class="edge ${esc(edge.kind)}" data-edge="${edge.id}" data-from="${edge.left_table_id}" data-to="${edge.right_table_id}" d="${edgePath(from, to)}">
        <title>${esc(edge.left_name)}.${esc(edge.left_column)} → ${esc(edge.right_name)}.${esc(edge.right_column)} · 包含度 ${(edge.containment * 100).toFixed(1)}%</title>
      </path>`;
    })
    .join('');
  const nodes =
    positions.map((node) => nodeMarkup(node, groups.secondary.some((item) => item.id === node.id) ? 'secondary' : 'primary')).join('');
  return `<svg viewBox="0 0 ${VIEW.w} ${VIEW.h}" role="img" aria-label="星型建模关系图，${data.edge_total} 条边">
    <g class="edges">${edges}</g>
    <g class="nodes">${nodes}</g>
  </svg>`;
}

function bindFocus(board) {
  const edges = Array.from(board.querySelectorAll('.edge'));
  board.querySelectorAll('.node').forEach((node) => {
    node.addEventListener('click', () => {
      const id = Number(node.dataset.node);
      const active = node.classList.contains('focus');
      board.querySelectorAll('.node').forEach((item) => item.classList.remove('focus'));
      edges.forEach((edge) => {
        edge.classList.remove('focus', 'faded');
      });
      if (active) return;
      node.classList.add('focus');
      edges.forEach((edge) => {
        const hit = Number(edge.dataset.from) === id || Number(edge.dataset.to) === id;
        edge.classList.add(hit ? 'focus' : 'faded');
      });
    });
  });
}

function openRelation(view, ctx, item) {
  const { root } = drawer({
    title: `${item.left_cn_name || item.left_table} → ${item.right_cn_name || item.right_table}`,
    subtitle: `${item.left_table}.${item.left_column} → ${item.right_table}.${item.right_column}`,
    body: `${kv([
      ['关系类型', `<span class="badge ${item.kind === 'pk-fk' ? 'fact' : 'warn'}">${esc(item.kind_label)}</span>`],
      ['包含度', `<span class="mono">${fmtRatio(item.containment)}</span>`],
      ['置信度', confidenceBar(item.confidence)],
      ['抽样行数', `<span class="mono">${esc(item.sample_size)}</span>`],
      ['左侧表', `<span class="mono">${esc(item.left_table)}</span>`],
      ['右侧表', `<span class="mono">${esc(item.right_table)}</span>`],
    ])}
    <h3>口径</h3>
    <pre class="code">左列去重样本值落在右列样本集合中的比例 = 包含度；
包含度 = 1.0 记主外键，0.98 ≤ 包含度 &lt; 1.0 记弱外键候选；
右侧必须是候选键（唯一率 = 1 且无空值），否则不计入关系。</pre>
    <h3>右侧字段剖析</h3>
    <div id="relation-profiles" class="mono muted">读取中…</div>`,
  });
  api
    .get('/api/profiles', { table_id: item.right_table_id, limit: 40 })
    .then((profiles) => {
      const holder = root.querySelector('#relation-profiles');
      if (!holder) return;
      holder.innerHTML = `<div class="table-wrap"><table class="data" style="min-width:0">
        <thead><tr><th>字段</th><th>类型</th><th>唯一率</th><th>基数</th></tr></thead>
        <tbody>${profiles.items
          .map(
            (profile) => `<tr style="cursor:default"><td class="mono">${esc(profile.column)}</td><td>${esc(profile.dtype_label)}</td><td class="num">${fmtRatio(profile.unique_ratio)}</td><td class="num">${esc(profile.cardinality)}</td></tr>`,
          )
          .join('')}</tbody></table></div>`;
    })
    .catch(() => {
      root.querySelector('#relation-profiles').textContent = '字段剖析读取失败';
    });
}

export const relationsPage = {
  async render(view, ctx) {
    let data;
    let list;
    try {
      [data, list] = await Promise.all([
        api.get('/api/relations/graph', { scope: state.scope || undefined }),
        api.get('/api/relations', { kind: state.kind, scope: state.scope || undefined, limit: 60 }),
      ]);
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => relationsPage.render(view, ctx));
      return;
    }
    const groups = groupNodes(data);
    const positions = [
      ...place(groups.secondary, 132),
      ...place(groups.primary, 452),
      ...place(groups.facts, 772),
    ];
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>关系图</h2>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <span class="meta" data-testid="graph-edge-count">${data.edge_total} 条边 · ${groups.facts.length} 事实 / ${groups.primary.length} 主维 / ${groups.secondary.length} 二级维</span>
            <span class="badge ${versionTone(data.version_status || '')}">${esc(ENUMS.versionStatus[data.version_status] || '—')} · ${esc(data.version_no || '—')}</span>
            <select id="scope-select" class="scope-select">
              <option value="" ${!state.scope ? 'selected' : ''}>正式版口径</option>
              <option value="draft" ${state.scope === 'draft' ? 'selected' : ''}>草案预览（未发布）</option>
            </select>
            ${can(ctx.user.role, 'export:read') ? '<button class="btn sm ghost" id="export-relations">导出关系 CSV</button>' : ''}
          </div>
        </div>
        <div class="graph-board" id="graph-board">${renderSvg(data, groups, positions)}</div>
        <div class="graph-legend">
          <span><i class="fact"></i>事实表（铜色）</span>
          <span><i></i>主外键（包含度 100%）</span>
          <span><i class="fk"></i>弱外键候选</span>
          <span class="muted">点击节点高亮它的边；无主键流水表未入图</span>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>包含依赖清单</h2><span class="meta">${list.total} 条</span></div>
        <div class="panel-body">
          <div class="filter-bar" id="relation-filters">
            ${field({ label: '关系类型', name: 'kind', value: state.kind, options: [{ value: '', label: '全部' }, ...Object.entries(ENUMS.relationKind).map(([value, label]) => ({ value, label }))] })}
          </div>
        </div>
        <div id="relation-list">${table({
          rows: list.items,
          empty: { title: '没有这类关系', hint: '切回全部，或执行一次剖析。' },
          columns: [
            { key: 'left_table', label: '左表（外键侧）', render: (row) => `<b>${esc(row.left_cn_name || row.left_table)}</b><div class="mono muted">${esc(row.left_table)}.${esc(row.left_column)}</div>` },
            { key: 'right_table', label: '右表（候选键侧）', render: (row) => `<b>${esc(row.right_cn_name || row.right_table)}</b><div class="mono muted">${esc(row.right_table)}.${esc(row.right_column)}</div>` },
            { key: 'kind_label', label: '类型', render: (row) => `<span class="badge ${row.kind === 'pk-fk' ? 'fact' : 'warn'}">${esc(row.kind_label)}</span>` },
            { key: 'containment', label: '包含度', className: 'num', render: (row) => fmtRatio(row.containment) },
            { key: 'confidence', label: '置信度', render: (row) => confidenceBar(row.confidence) },
            { key: 'sample_size', label: '抽样', className: 'num' },
          ],
        })}</div>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>未入图的贴源表</h2><span class="meta">${groups.unrelated.length} 张</span></div>
        <div class="panel-body" style="display:flex;flex-wrap:wrap;gap:8px">
          ${groups.unrelated
            .map(
              (node) => `<span class="badge">${esc(node.cn_name)} <span class="mono muted">${esc(node.name)}</span></span>`,
            )
            .join('') || '<span class="muted">全部表都已入图。</span>'}
        </div>
      </section>`;

    bindFocus(view.querySelector('#graph-board'));
    view.querySelector('#scope-select')?.addEventListener('change', (event) => {
      state.scope = event.target.value;
      relationsPage.render(view, ctx);
    });
    const filters = view.querySelector('#relation-filters');
    filters?.addEventListener('change', () => {
      state.kind = filters.querySelector('[name=kind]').value;
      relationsPage.render(view, ctx);
    });
    view.querySelectorAll('#relation-list table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const item = list.items.find((entry) => String(entry.id) === row.dataset.id);
        if (item) openRelation(view, ctx, item);
      });
    });
    view.querySelector('#export-relations')?.addEventListener('click', async () => {
      try {
        await api.download('/api/exports/relations.csv', 'starmodel-relations.csv');
        toast('已开始下载关系清单');
      } catch (err) {
        toast(errorMessage(err), 'err');
      }
    });
  },
};

export default relationsPage;
