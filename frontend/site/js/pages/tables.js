import { api } from '../api.js';
import { ENUMS, can } from '../config.js';
import { drawer, errorBox, errorMessage, esc, field, fmtNumber, fmtRatio, fmtTime, kv, table, toast } from '../ui.js';

const state = { q: '', domain: '' };

function profileTable(items) {
  if (!items.length) return '<p class="muted">该表还没有剖析结果。</p>';
  return `<div class="table-wrap"><table class="data" style="min-width:0">
    <thead><tr><th>字段</th><th>类型</th><th>唯一率</th><th>空值率</th><th>基数</th><th>样本值</th></tr></thead>
    <tbody>${items
      .map(
        (item) => `<tr style="cursor:default">
          <td class="mono">${esc(item.column)}</td>
          <td>${esc(item.dtype_label)}</td>
          <td class="num">${fmtRatio(item.unique_ratio)}</td>
          <td class="num">${fmtRatio(item.null_ratio)}</td>
          <td class="num">${esc(item.cardinality)}</td>
          <td class="mono muted">${esc((item.sample_values || []).slice(0, 4).join(' / '))}</td>
        </tr>`,
      )
      .join('')}</tbody></table></div>`;
}

function openTable(view, ctx, tableId) {
  api
    .get(`/api/source-tables/${tableId}`)
    .then((detail) => {
      const { root } = drawer({
        title: `${detail.cn_name}`,
        subtitle: `${detail.name} · ${detail.domain_label} · ${detail.profile_count} 个字段`,
        body: `${kv([
          ['表名', `<span class="mono">${esc(detail.name)}</span>`],
          ['主题域', esc(detail.domain_label)],
          ['行数', `<span class="mono">${fmtNumber(detail.row_count)}</span>`],
          ['字段数', esc(detail.field_count)],
          ['抽样行', esc(detail.sample_count)],
          ['最近剖析', fmtTime(detail.scanned_at)],
          ['备注', esc(detail.note || '—')],
        ])}
        <h3>字段剖析（唯一率 / 空值率 / 基数）</h3>
        ${profileTable(detail.profiles)}
        <h3>抽样首行</h3>
        <pre class="code">${esc(JSON.stringify(detail.sample_preview?.[0] || {}, null, 2))}</pre>`,
        footer: '<span class="mono muted">剖析结果由后端 GET /api/profiles 与运行日志计算，前端只展示。</span>',
      });
      root.addEventListener('click', (event) => {
        if (event.target.closest('[data-close]')) event.preventDefault();
      });
    })
    .catch((err) => toast(errorMessage(err), 'err'));
}

function openCreate(view, ctx) {
  const { root, close } = drawer({
    title: '登记贴源表',
    subtitle: '新表登记后会被下一次剖析纳入（自然键为表名，重复登记返回 409）',
    body: `<form id="table-form" style="display:grid;gap:12px">
      ${field({ label: '表名（小写字母/数字/下划线）', name: 'name', placeholder: 'ods_new_table' })}
      ${field({ label: '中文名', name: 'cn_name', placeholder: '新接入表' })}
      ${field({ label: '主题域', name: 'domain', value: 'sales', options: Object.entries(ENUMS.domain).map(([value, label]) => ({ value, label })) })}
      ${field({ label: '主题（用于生成 dwd_<subject>_fact）', name: 'subject', placeholder: 'new' })}
      <div class="form-error" id="table-error"></div>
      <button class="btn accent" type="submit">登记并剖析字段</button>
    </form>`,
  });
  root.querySelector('#table-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      await api.post('/api/source-tables', {
        name: form.name.value.trim(),
        cn_name: form.cn_name.value.trim(),
        domain: form.domain.value,
        subject: form.subject.value.trim() || form.name.value.trim(),
        sample_rows: [],
      });
      toast('贴源表已登记');
      close();
      await tablesPage.render(view, ctx);
    } catch (err) {
      root.querySelector('#table-error').textContent =
        err.code === 'CONFLICT' ? '表名已存在（409）' : errorMessage(err);
    }
  });
}

export const tablesPage = {
  async render(view, ctx) {
    let data;
    try {
      data = await api.get('/api/source-tables', { q: state.q, domain: state.domain, limit: 50 });
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => tablesPage.render(view, ctx));
      return;
    }
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>贴源表与剖析</h2>
          <div style="display:flex;gap:8px;align-items:center">
            <span class="meta">${data.total} 张 · 每列最多抽样 200 行</span>
            ${can(ctx.user.role, 'table:write') ? '<button class="btn sm accent" id="new-table">登记贴源表</button>' : ''}
          </div>
        </div>
        <div class="panel-body">
          <div class="filter-bar" id="table-filters">
            ${field({ label: '搜索', name: 'q', value: state.q, placeholder: '表名 / 中文名' })}
            ${field({ label: '主题域', name: 'domain', value: state.domain, options: [{ value: '', label: '全部' }, ...Object.entries(ENUMS.domain).map(([value, label]) => ({ value, label }))] })}
          </div>
        </div>
        ${table({
          rows: data.items,
          empty: { title: '没有匹配的贴源表', hint: '换个关键词，或先执行一次剖析。' },
          columns: [
            { key: 'cn_name', label: '中文名', render: (row) => `<b>${esc(row.cn_name)}</b><div class="mono muted">${esc(row.name)}</div>` },
            { key: 'domain_label', label: '主题域', render: (row) => `<span class="badge info">${esc(row.domain_label)}</span>` },
            { key: 'row_count', label: '行数', className: 'num', render: (row) => fmtNumber(row.row_count) },
            { key: 'field_count', label: '字段', className: 'num' },
            { key: 'profile_count', label: '剖析列', className: 'num' },
            { key: 'scanned_at', label: '最近剖析', render: (row) => fmtTime(row.scanned_at) },
          ],
        })}
      </section>
      <p class="mono muted">点击任意一行查看逐列剖析；唯一率 = 去重值 / 抽样行数，空值率 = 空值行 / 抽样行。</p>`;

    const filters = view.querySelector('#table-filters');
    filters?.addEventListener('change', () => {
      state.q = filters.querySelector('[name=q]').value.trim();
      state.domain = filters.querySelector('[name=domain]').value;
      tablesPage.render(view, ctx);
    });
    filters?.querySelector('[name=q]')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        state.q = event.target.value.trim();
        tablesPage.render(view, ctx);
      }
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => openTable(view, ctx, row.dataset.id));
    });
    view.querySelector('#new-table')?.addEventListener('click', () => openCreate(view, ctx));
  },
};

export default tablesPage;
