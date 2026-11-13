import { api } from '../api.js';
import { ENUMS, can, changeTone, versionTone } from '../config.js';
import { drawer, errorBox, errorMessage, esc, field, fmtTime, kv, table, toast } from '../ui.js';

const state = { status: '' };

function validationBlock(validation) {
  if (!validation || !validation.checks) return '<p class="muted">暂无核对结果。</p>';
  const rows = validation.checks
    .map(
      (check) => `<tr style="cursor:default">
        <td><span class="badge ${check.passed ? 'ok' : 'danger'}">${check.passed ? '通过' : '未过'}</span></td>
        <td>${esc(check.label)}</td>
        <td class="mono muted">${esc(JSON.stringify(check.detail || {}))}</td>
      </tr>`,
    )
    .join('');
  return `<div class="table-wrap"><table class="data" style="min-width:0">
    <thead><tr><th>结果</th><th>核对项</th><th>依据 / 违例</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

function diffSummaryBlock(version) {
  const s = version.diff_summary || {};
  const sug = s.suggestions || {};
  const rel = s.relations || {};
  return kv([
    [
      '建议差异',
      `<span class="badge ok">新增 ${sug.added ?? 0}</span>
       <span class="badge warn">变更 ${sug.changed ?? 0}</span>
       <span class="badge danger">移除 ${sug.removed ?? 0}</span>
       <span class="badge info">无变化 ${sug.unchanged ?? 0}</span>`,
    ],
    [
      '关系差异',
      `<span class="badge ok">新增 ${rel.added ?? 0}</span>
       <span class="badge warn">变更 ${rel.changed ?? 0}</span>
       <span class="badge danger">移除 ${rel.removed ?? 0}</span>
       <span class="badge info">无变化 ${rel.unchanged ?? 0}</span>`,
    ],
    ['对比基线', esc(s.base_version_no || '（首个版本，无基线）')],
    ['补数范围', (s.affected_table_ids || []).length ? esc(`${(s.affected_table_ids || []).length} 张受影响表`) : '全量剖析'],
  ]);
}

function evidenceBlock(items) {
  const rows = items
    .map(
      (item) => `<tr style="cursor:default">
        <td><span class="badge ${changeTone(item.change_kind)}">${esc(item.change_label)}</span></td>
        <td><b class="mono">${esc(item.target_name || '—')}</b><div class="mono muted">${esc(item.table_name || '')}</div></td>
        <td>${esc(item.grain || item.base_grain || '—')}</td>
        <td class="num">${item.confidence === null || item.confidence === undefined ? '—' : esc(item.confidence)}</td>
        <td class="num">${item.base_confidence === null || item.base_confidence === undefined ? '—' : esc(item.base_confidence)}</td>
        <td><span class="badge ${statusToneSafe(item.status)}">${esc(item.status_label || '—')}</span></td>
      </tr>`,
    )
    .join('');
  return `<div class="table-wrap"><table class="data" style="min-width:0">
    <thead><tr><th>差异</th><th>建议</th><th>本版粒度</th><th>本版置信度</th><th>基线置信度</th><th>人工决定</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

function statusToneSafe(status) {
  return { pending: 'warn', adopted: 'ok', dismissed: 'danger' }[status] || 'info';
}

function relationDiffBlock(items) {
  const rows = items
    .map(
      (item) => `<tr style="cursor:default">
        <td><span class="badge ${changeTone(item.kind)}">${esc(ENUMS.changeKind[item.kind] || item.kind)}</span></td>
        <td class="mono">${esc((item.edge || []).join(' . '))}</td>
        <td class="num">${item.containment === null || item.containment === undefined ? '—' : `${(item.containment * 100).toFixed(1)}%`}</td>
        <td class="num">${item.base_containment === null || item.base_containment === undefined ? '—' : `${(item.base_containment * 100).toFixed(1)}%`}</td>
      </tr>`,
    )
    .join('');
  return `<div class="table-wrap"><table class="data" style="min-width:0">
    <thead><tr><th>差异</th><th>边（左表.左列 → 右表.右列）</th><th>本版包含度</th><th>基线包含度</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

async function openVersion(view, ctx, versionId) {
  let detail;
  let diff;
  try {
    [detail, diff] = await Promise.all([
      api.get(`/api/analysis-versions/${versionId}`),
      api.get(`/api/analysis-versions/${versionId}/diff`),
    ]);
  } catch (err) {
    toast(errorMessage(err), 'err');
    return;
  }
  const canPublish = can(ctx.user.role, 'version:release') && detail.status === 'draft';
  const canRevalidate = can(ctx.user.role, 'run:create') && detail.status === 'validation_failed';
  const changedSuggestions = diff.suggestions.filter((item) => item.change_kind !== 'unchanged');
  const changedRelations = diff.relations.filter((item) => item.kind !== 'unchanged');
  const { root, close } = drawer({
    title: `${detail.version_no}`,
    subtitle: `${detail.status_label} · ${ENUMS.trigger[detail.trigger] || detail.trigger} · ${esc(detail.operator_email)}`,
    body: `${kv([
      ['版本号', `<span class="mono">${esc(detail.version_no)}</span>`],
      ['状态', `<span class="badge ${versionTone(detail.status)}">${esc(detail.status_label)}</span>`],
      ['触发', esc(ENUMS.trigger[detail.trigger] || detail.trigger)],
      ['规模', `${detail.table_count} 表 / ${detail.profile_count} 字段 / ${detail.relation_count} 关系 / ${detail.suggestion_count} 建议`],
      ['生成时间', fmtTime(detail.created_at)],
      ['发布人', esc(detail.published_by || '—')],
      ['发布时间', fmtTime(detail.published_at)],
      ['运行日志', `<span class="mono muted">${esc(detail.log_text || '')}</span>`],
    ])}
    <h3>差异摘要（对比 ${esc(diff.base_version?.version_no || '无基线')}）</h3>
    ${diffSummaryBlock(detail)}
    <h3>关系与粒度核对 · 本版依据</h3>
    ${validationBlock(detail.validation)}
    <h3>建议差异（${changedSuggestions.length} 条有变化）</h3>
    ${changedSuggestions.length ? evidenceBlock(changedSuggestions) : '<p class="muted">所有建议与基线一致。</p>'}
    <h3>关系差异（${changedRelations.length} 条有变化）</h3>
    ${changedRelations.length ? relationDiffBlock(changedRelations) : '<p class="muted">所有关系边与基线一致。</p>'}`,
    footer: `
      ${canPublish ? '<button class="btn accent" id="publish-btn">核对无误，发布为正式版</button>' : ''}
      ${canRevalidate ? '<button class="btn ghost" id="revalidate-btn">重新核对</button>' : ''}
      ${!canPublish && !canRevalidate ? '<span class="mono muted">该版本为只读留档（正式版/历史版），或当前角色无发布权限。</span>' : ''}`,
  });
  root.querySelector('#publish-btn')?.addEventListener('click', async () => {
    try {
      await api.post(`/api/analysis-versions/${versionId}/publish`, {});
      toast(`已发布 ${detail.version_no}：建议、关系图与 DDL 已一次性切换`);
      close();
      await versionsPage.render(view, ctx);
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
  root.querySelector('#revalidate-btn')?.addEventListener('click', async () => {
    try {
      const result = await api.post(`/api/analysis-versions/${versionId}/revalidate`, {});
      toast(result.validation?.passed ? '核对通过，草案可发布' : '核对仍未通过');
      close();
      await versionsPage.render(view, ctx);
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
}

function openIncremental(view, ctx, tables) {
  const options = tables.map((item) => ({ value: item.id, label: `${item.cn_name}（${item.name}）` }));
  const { root, close } = drawer({
    title: '补数增量剖析',
    subtitle: '只重算勾选业务对象的建议，其余沿用上一正式版；产物仍是待核对草案',
    body: `<form id="incremental-form" style="display:grid;gap:12px">
      <div class="field">
        <label>受影响的贴源表（可多选，按住 Ctrl/Cmd）</label>
        <select name="affected" id="affected-select" multiple size="8" style="width:100%">
          ${options.map((opt) => `<option value="${esc(opt.value)}">${esc(opt.label)}</option>`).join('')}
        </select>
      </div>
      <p class="mono muted">未勾选的表其剖析、关系与建议直接沿用当前正式版快照，不会被整批换新。</p>
      <div class="form-error" id="incremental-error"></div>
      <button class="btn accent" type="submit">生成增量草案</button>
    </form>`,
  });
  root.querySelector('#incremental-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const selected = Array.from(root.querySelector('#affected-select').selectedOptions).map((opt) => Number(opt.value));
    if (!selected.length) {
      root.querySelector('#incremental-error').textContent = '请至少选择一张受影响表';
      return;
    }
    try {
      const run = await api.post('/api/analysis-versions/incremental-run', { affected_table_ids: selected });
      toast(`增量草案已生成：${run.suggestion_count} 条建议，运行 ${run.run_no}`);
      close();
      await versionsPage.render(view, ctx);
    } catch (err) {
      root.querySelector('#incremental-error').textContent = errorMessage(err);
    }
  });
}

export const versionsPage = {
  async render(view, ctx) {
    let data;
    let overview;
    let tables;
    try {
      [data, overview, tables] = await Promise.all([
        api.get('/api/analysis-versions', { status: state.status, limit: 30 }),
        api.get('/api/overview'),
        api.get('/api/source-tables', { limit: 50 }),
      ]);
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => versionsPage.render(view, ctx));
      return;
    }
    const published = data.items.find((item) => item.status === 'published');
    const draft = data.items.find((item) => item.status === 'draft' || item.status === 'validation_failed');
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>分析版本（草案 → 核对 → 正式版）</h2>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            ${can(ctx.user.role, 'run:create') ? '<button class="btn sm ghost" id="rerun-full">全量重新剖析</button>' : ''}
            ${can(ctx.user.role, 'run:create') ? '<button class="btn sm accent" id="rerun-incremental">补数增量剖析</button>' : ''}
          </div>
        </div>
        <div class="panel-body">
          <div class="filter-bar" id="version-filters">
            ${field({ label: '状态', name: 'status', value: state.status, options: [{ value: '', label: '全部' }, ...Object.entries(ENUMS.versionStatus).map(([value, label]) => ({ value, label }))] })}
            <div class="spacer"></div>
            <span class="mono muted">正式版：${published ? esc(published.version_no) : '暂无'} · 待核对草案：${draft ? esc(draft.version_no) : '暂无'}</span>
          </div>
        </div>
        ${table({
          rows: data.items,
          empty: { title: '还没有分析版本', hint: '执行一次剖析，后端会生成可核对的草案。' },
          columns: [
            { key: 'version_no', label: '版本号', render: (row) => `<b class="mono">${esc(row.version_no)}</b><div class="mono muted">${fmtTime(row.created_at)}</div>` },
            { key: 'status', label: '状态', render: (row) => `<span class="badge ${versionTone(row.status)}">${esc(row.status_label)}</span>` },
            { key: 'trigger', label: '触发', render: (row) => esc(ENUMS.trigger[row.trigger] || row.trigger) },
            { key: 'scale', label: '规模', className: 'mono', render: (row) => `${row.relation_count} 关系 / ${row.suggestion_count} 建议` },
            {
              key: 'diff',
              label: '建议差异',
              render: (row) => {
                const s = row.diff_summary?.suggestions;
                if (!s) return '<span class="muted">—</span>';
                return `<span class="badge ok">+${s.added ?? 0}</span> <span class="badge warn">~${s.changed ?? 0}</span> <span class="badge danger">-${s.removed ?? 0}</span>`;
              },
            },
            {
              key: 'validation',
              label: '核对',
              render: (row) => (row.validation?.passed === undefined ? '<span class="muted">—</span>' : `<span class="badge ${row.validation.passed ? 'ok' : 'danger'}">${row.validation.passed ? '通过' : `未过 ${row.validation.failed_checks.length} 项`}</span>`),
            },
            { key: 'published_by', label: '发布人', render: (row) => `<span class="mono muted">${esc(row.published_by || '—')}</span>` },
          ],
        })}
      </section>
      <p class="mono muted">
        草案通过关系与粒度核对后，由管理员一次性发布：建议、关系图与 DDL 在单事务内切换，失败自动恢复上一正式版；
        人工采纳/驳回按业务对象迁移，重跑与补数都不会重置。当前口径版本：${overview.scope_version ? esc(overview.scope_version.version_no) : '暂无'}。
      </p>`;

    view.querySelector('#version-filters')?.addEventListener('change', () => {
      state.status = view.querySelector('[name=status]').value;
      versionsPage.render(view, ctx);
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const item = data.items.find((entry) => String(entry.id) === row.dataset.id);
        if (item) openVersion(view, ctx, item.id);
      });
    });
    view.querySelector('#rerun-full')?.addEventListener('click', async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = '剖析中…';
      try {
        const run = await api.post('/api/model-runs', { trigger: 'manual' });
        toast(run.version_id ? `草案已生成（运行 ${run.run_no}），请核对后发布` : `剖析完成：${run.suggestion_count} 条建议`);
        await versionsPage.render(view, ctx);
      } catch (err) {
        toast(errorMessage(err), 'err');
        button.disabled = false;
        button.textContent = '全量重新剖析';
      }
    });
    view.querySelector('#rerun-incremental')?.addEventListener('click', () => {
      openIncremental(view, ctx, tables.items);
    });
  },
};

export default versionsPage;
