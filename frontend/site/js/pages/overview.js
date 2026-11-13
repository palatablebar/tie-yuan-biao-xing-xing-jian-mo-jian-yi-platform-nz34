import { api } from '../api.js';
import { can, runTone } from '../config.js';
import { barList, emptyState, errorBox, errorMessage, esc, fmtTime, statStrip, toast, trendChart } from '../ui.js';

function acceptancePanel(latest, data) {
  const metrics = latest?.metrics || {};
  const rows = [
    ['事实表', metrics.fact_tables ?? data.fact_total],
    ['维度表', metrics.dim_total ?? data.dim_total],
    ['二级维（雪花）', metrics.secondary_dims ?? data.secondary_dim_total],
    ['无关表', metrics.unrelated_tables ?? data.unrelated_total],
    ['关系包含度均值', metrics.avg_relation_confidence ? metrics.avg_relation_confidence.toFixed(3) : '—'],
    ['被拒的同名候选对', metrics.rejected_pairs ?? '—'],
    ['迁移的人工决定', metrics.migrated_decisions ?? 0],
  ];
  return `<div class="panel">
    <div class="panel-head"><h2>本次判定口径</h2><span class="meta">classification</span></div>
    <div class="panel-body">
      ${latest ? `<dl class="kv">${rows
        .map(([key, value]) => `<dt>${esc(key)}</dt><dd class="mono">${esc(value)}</dd>`)
        .join('')}</dl>` : emptyState({ title: '还没有剖析运行', hint: '点右上角「执行剖析」，后端会生成待核对草案。' })}
    </div>
  </div>`;
}

export const overviewPage = {
  async render(view, ctx) {
    view.innerHTML = '<div class="empty"><div class="mark">读取制图台…</div></div>';
    let data;
    try {
      data = await api.get('/api/overview');
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => overviewPage.render(view, ctx));
      return;
    }
    const latest = data.latest_run;
    const scope = data.scope_version;
    const draft = data.draft_version;
    view.innerHTML = `
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap">
        <div class="eyebrow" data-testid="overview-lead">制图台 · ${data.tables_total} 张贴源表 / ${data.relations_total} 条包含依赖 / ${data.suggestions_total} 条建议</div>
        <div style="display:flex;gap:8px">
          ${can(ctx.user.role, 'run:create') ? '<button class="btn sm accent" id="run-profiling" data-testid="run-profiling">执行剖析（生成草案）</button>' : ''}
          <button class="btn sm ghost" id="go-versions">分析版本</button>
          <button class="btn sm ghost" id="go-graph">打开关系图</button>
        </div>
      </div>
      ${
        draft
          ? `<div class="draft-banner" style="margin:12px 0">
               <span>待核对草案 <b class="mono">${esc(draft.version_no)}</b>（${esc(draft.status_label)}）尚未发布，当前关系图/建议/DDL 仍取正式版。</span>
               <button class="btn sm ghost" id="go-publish">去核对并发布</button>
             </div>`
          : ''
      }
      ${statStrip([
        { label: '贴源表', value: data.tables_total, hint: `${data.profiles_total} 个字段完成剖析` },
        { label: '关系边', value: data.relations_total, hint: '同名键 + 包含度 ≥ 0.98' },
        { label: '建模建议', value: data.suggestions_total, hint: `${data.pending_total} 条待采纳 · ${data.adopted_total} 条已采纳` },
        { label: '正式版', value: scope ? scope.version_no : '暂无', hint: scope ? `${scope.status_label} · ${scope.relation_count} 关系` : '尚未发布' },
      ])}
      <div class="grid-3">
        <section class="panel">
          <div class="panel-head"><h2>关系类型</h2><span class="meta">containment</span></div>
          <div class="panel-body">${
            data.relation_kinds.some((item) => item.count)
              ? barList(data.relation_kinds)
              : emptyState({ title: '还没有关系边', hint: '执行一次剖析。' })
          }</div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>建议状态</h2><span class="meta">adoption</span></div>
          <div class="panel-body">${
            data.suggestion_status.some((item) => item.count)
              ? barList(data.suggestion_status, 'ok')
              : emptyState({ title: '还没有建议', hint: '剖析完成后自动生成。' })
          }</div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>主题域</h2><span class="meta">domains</span></div>
          <div class="panel-body">${barList(data.domains)}</div>
        </section>
      </div>
      <div class="grid-2">
        <section class="panel">
          <div class="panel-head"><h2>最近一次剖析</h2><span class="meta">latest run</span></div>
          <div class="panel-body">
            ${
              latest
                ? `<div class="kv">
                    <dt>运行号</dt><dd class="mono">${esc(latest.run_no)}</dd>
                    <dt>状态</dt><dd><span class="badge ${runTone(latest.status)}">${esc(latest.status_label)}</span></dd>
                    <dt>触发</dt><dd>${esc(latest.trigger_label)} · ${esc(latest.operator_email)}</dd>
                    <dt>规模</dt><dd class="mono">${latest.table_count} 表 / ${latest.profile_count} 字段 / ${latest.relation_count} 关系</dd>
                    <dt>建议</dt><dd class="mono">${latest.suggestion_count} 条 · 草案版本 #${esc(latest.version_id ?? '—')}</dd>
                    <dt>开始</dt><dd>${fmtTime(latest.started_at)}</dd>
                    <dt>日志</dt><dd class="mono muted">${esc(latest.log_text || '')}</dd>
                  </div>`
                : emptyState({ title: '还没有运行', hint: '管理员或建模专员可以执行剖析。' })
            }
          </div>
        </section>
        ${acceptancePanel(latest, data)}
      </div>
      <section class="panel">
        <div class="panel-head"><h2>近 7 天剖析次数</h2><span class="meta">runs / day</span></div>
        <div class="panel-body">${trendChart(data.trend)}</div>
      </section>
      <p class="mono muted">全部数字来自 <code>GET /api/overview</code>，按当前正式版分析版本统计；草案经关系与粒度核对并发布后才会切换口径。</p>`;

    view.querySelector('#go-graph')?.addEventListener('click', () => {
      location.hash = '#/relations';
    });
    view.querySelector('#go-versions')?.addEventListener('click', () => {
      location.hash = '#/versions';
    });
    view.querySelector('#go-publish')?.addEventListener('click', () => {
      location.hash = '#/versions';
    });
    view.querySelector('#run-profiling')?.addEventListener('click', async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = '剖析中…';
      try {
        const run = await api.post('/api/model-runs', { trigger: 'manual' });
        toast(`草案已生成：${run.relation_count} 条关系 / ${run.suggestion_count} 条建议，请核对后发布`);
        await overviewPage.render(view, ctx);
      } catch (err) {
        toast(errorMessage(err), 'err');
        button.disabled = false;
        button.textContent = '执行剖析（生成草案）';
      }
    });
  },
};

export default overviewPage;
