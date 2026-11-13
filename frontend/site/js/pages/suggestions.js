import { api } from '../api.js';
import { ENUMS, can, roleTone, statusTone } from '../config.js';
import { confidenceBar, drawer, errorBox, errorMessage, esc, field, kv, table, toast } from '../ui.js';

const state = { role: '', status: '', q: '' };

function joinsTable(joins) {
  if (!joins || !joins.length) return '<p class="muted">该建议没有关联边（独立表或二级维）。</p>';
  return `<div class="table-wrap"><table class="data" style="min-width:0">
    <thead><tr><th>维度/事实</th><th>关联列</th><th>目标列</th><th>包含度</th></tr></thead>
    <tbody>${joins
      .map(
        (join) => `<tr style="cursor:default">
          <td>${esc(join.dim_target || join.fact_table || join.dim_table)}</td>
          <td class="mono">${esc(join.fact_column)}</td>
          <td class="mono">${esc(join.dim_column)}</td>
          <td class="num">${join.containment === undefined ? '—' : `${(join.containment * 100).toFixed(1)}%`}</td>
        </tr>`,
      )
      .join('')}</tbody></table></div>`;
}

function openSuggestion(view, ctx, item) {
  const adoptable = can(ctx.user.role, 'suggestion:adopt') && item.status === 'pending';
  const dismissable = can(ctx.user.role, 'suggestion:review') && item.status !== 'adopted';
  const { root, close } = drawer({
    title: `${item.target_name}`,
    subtitle: `${item.table_name} → ${item.role_label} · ${item.status_label}`,
    body: `${kv([
      ['目标表', `<span class="mono">${esc(item.target_name)}</span>`],
      ['源表', `<span class="mono">${esc(item.table_name)}</span>`],
      ['角色', `<span class="badge ${roleTone(item.role)}">${esc(item.role_label)}</span>`],
      ['粒度', esc(item.grain)],
      ['置信度', confidenceBar(item.confidence)],
      ['状态', `<span class="badge ${statusTone(item.status)}">${esc(item.status_label)}</span>`],
      ['度量列', `<span class="mono">${esc((item.measures || []).join(' / ') || '—')}</span>`],
      ['属性列', `<span class="mono">${esc((item.attributes || []).slice(0, 8).join(' / ') || '—')}</span>`],
      ['采纳人', esc(item.adopted_by || '—')],
      ['判定依据', esc(item.reason)],
    ])}
    <h3>关联边</h3>
    ${joinsTable(item.joins)}
    <h3>CREATE TABLE DDL（后端生成）</h3>
    <pre class="code">${esc(item.ddl)}</pre>`,
    footer: `${adoptable ? '<button class="btn accent" id="adopt-btn">采纳这条建议</button>' : ''}
      ${dismissable ? '<button class="btn ghost" id="dismiss-btn" style="margin-left:8px">驳回</button>' : ''}
      ${!adoptable && !dismissable ? '<span class="mono muted">当前角色无采纳/驳回权限，或该建议已定稿。</span>' : ''}`,
  });
  root.querySelector('#adopt-btn')?.addEventListener('click', async () => {
    try {
      await api.post(`/api/model-suggestions/${item.id}/adopt`, {});
      toast(`已采纳 ${item.target_name}`);
      close();
      await suggestionsPage.render(view, ctx);
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
  root.querySelector('#dismiss-btn')?.addEventListener('click', async () => {
    try {
      await api.post(`/api/model-suggestions/${item.id}/dismiss`, {});
      toast(`已驳回 ${item.target_name}`);
      close();
      await suggestionsPage.render(view, ctx);
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
}

export const suggestionsPage = {
  async render(view, ctx) {
    let data;
    let overview;
    try {
      [data, overview] = await Promise.all([
        api.get('/api/model-suggestions', { role: state.role, status: state.status, q: state.q, limit: 40 }),
        api.get('/api/overview'),
      ]);
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => suggestionsPage.render(view, ctx));
      return;
    }
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>星型建模建议</h2>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <span class="meta">${data.total} 条 · 4 事实 / 5 主维 · 7 张二级维不单独建议</span>
            ${can(ctx.user.role, 'run:create') ? '<button class="btn sm ghost" id="rerun">重新剖析</button>' : ''}
            ${can(ctx.user.role, 'export:read') ? '<button class="btn sm accent" id="export-ddl" data-testid="export-ddl">导出 DDL</button>' : ''}
          </div>
        </div>
        <div class="panel-body">
          <div class="filter-bar" id="suggestion-filters">
            ${field({ label: '搜索', name: 'q', value: state.q, placeholder: '目标表 / 粒度' })}
            ${field({ label: '角色', name: 'role', value: state.role, options: [{ value: '', label: '全部' }, ...Object.entries(ENUMS.suggestionRole).map(([value, label]) => ({ value, label }))] })}
            ${field({ label: '状态', name: 'status', value: state.status, options: [{ value: '', label: '全部' }, ...Object.entries(ENUMS.suggestionStatus).map(([value, label]) => ({ value, label }))] })}
            <div class="spacer"></div>
            <span class="mono muted">待采纳 ${overview.pending_total} · 已采纳 ${overview.adopted_total}</span>
          </div>
        </div>
        ${table({
          rows: data.items,
          empty: { title: '没有匹配的建议', hint: '换一个角色或状态筛选。' },
          columns: [
            { key: 'target_name', label: '目标表', render: (row) => `<b class="mono">${esc(row.target_name)}</b><div class="mono muted">${esc(row.table_name)}</div>` },
            { key: 'role', label: '角色', render: (row) => `<span class="badge ${roleTone(row.role)}">${esc(row.role_label)}</span>` },
            { key: 'grain', label: '粒度', render: (row) => `<span>${esc(row.grain)}</span>` },
            { key: 'joins', label: '关联', className: 'num', render: (row) => (row.joins || []).length },
            { key: 'confidence', label: '置信度', render: (row) => confidenceBar(row.confidence) },
            { key: 'status', label: '状态', render: (row) => `<span class="badge ${statusTone(row.status)}">${esc(row.status_label)}</span>` },
            { key: 'adopted_by', label: '采纳人', render: (row) => `<span class="mono muted">${esc(row.adopted_by || '—')}</span>` },
          ],
        })}
      </section>
      <p class="mono muted">建议与 DDL 全部由后端算法生成并落库；采纳只改状态，不改算法结论。导出 SQL 共 9 段，每段一条建议。</p>`;

    const filters = view.querySelector('#suggestion-filters');
    filters?.addEventListener('change', () => {
      state.q = filters.querySelector('[name=q]').value.trim();
      state.role = filters.querySelector('[name=role]').value;
      state.status = filters.querySelector('[name=status]').value;
      suggestionsPage.render(view, ctx);
    });
    filters?.querySelector('[name=q]')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        state.q = event.target.value.trim();
        suggestionsPage.render(view, ctx);
      }
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const item = data.items.find((entry) => String(entry.id) === row.dataset.id);
        if (item) openSuggestion(view, ctx, item);
      });
    });
    view.querySelector('#export-ddl')?.addEventListener('click', async () => {
      try {
        await api.download('/api/exports/ddl.sql', 'starmodel-ddl.sql');
        toast('已开始下载 DDL（9 段）');
      } catch (err) {
        toast(errorMessage(err), 'err');
      }
    });
    view.querySelector('#rerun')?.addEventListener('click', async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = '剖析中…';
      try {
        const run = await api.post('/api/model-runs', { trigger: 'manual' });
        toast(`重新剖析完成：${run.suggestion_count} 条建议`);
        await suggestionsPage.render(view, ctx);
      } catch (err) {
        toast(errorMessage(err), 'err');
        button.disabled = false;
        button.textContent = '重新剖析';
      }
    });
  },
};

export default suggestionsPage;
