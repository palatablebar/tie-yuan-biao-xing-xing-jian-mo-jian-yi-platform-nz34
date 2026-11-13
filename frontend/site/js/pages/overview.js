import { api } from '../api.js';
import { can, runTone } from '../config.js';
import { barList, emptyState, errorBox, errorMessage, esc, fmtNumber, fmtTime, statStrip, toast, trendChart } from '../ui.js';

function acceptancePanel(latest, data) {
  const metrics = latest?.metrics || {};
  const rows = [
    ['事实表', metrics.fact_tables ?? data.fact_total],
    ['维度表', metrics.dim_tables ?? data.dim_total],
    ['二级维（雪花）', metrics.secondary_dims ?? data.secondary_dim_total],
    ['无关表', metrics.unrelated_tables ?? data.unrelated_total],
    ['关系包含度均值', metrics.avg_relation_confidence ? metrics.avg_relation_confidence.toFixed(3) : '—'],
    ['被拒的同名候选对', metrics.rejected_pairs ?? '—'],
  ];
  return `<div class="panel">
    <div class="panel-head"><h2>本次判定口径</h2><span class="meta">classification</span></div>
    <div class="panel-body">
      ${latest ? `<dl class="kv">${rows
        .map(([key, value]) => `<dt>${esc(key)}</dt><dd class="mono">${esc(value)}</dd>`)
        .join('')}</dl>` : emptyState({ title: '还没有剖析运行', hint: '点右上角「执行剖析」，后端会重新算一遍。' })}
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
    view.innerHTML = `
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap">
        <div class="eyebrow" data-testid="overview-lead">制图台 · 24 张贴源表 / 18 条包含依赖 / 9 条建议</div>
        <div style="display:flex;gap:8px">
          ${can(ctx.user.role, 'run:create') ? '<button class="btn sm accent" id="run-profiling" data-testid="run-profiling">执行剖析</button>' : ''}
          <button class="btn sm ghost" id="go-graph">打开关系图</button>
        </div>
      </div>
      ${statStrip([
        { label: '贴源表', value: data.tables_total, hint: `${data.profiles_total} 个字段完成剖析` },
        { label: '关系边', value: data.relations_total, hint: '同名键 + 包含度 ≥ 0.98' },
        { label: '建模建议', value: data.suggestions_total, hint: `${data.pending_total} 条待采纳 · ${data.adopted_total} 条已采纳` },
        { label: 'worker', value: data.worker_alive ? '在岗' : '离线', hint: latest ? `最近剖析 ${latest.run_no}` : '尚无运行' },
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
                    <dt>建议</dt><dd class="mono">${latest.suggestion_count} 条</dd>
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
      <p class="mono muted">全部数字来自 <code>GET /api/overview</code>，由后端按库内剖析结果统计；前端不做任何算法推导。</p>`;

    view.querySelector('#go-graph')?.addEventListener('click', () => {
      location.hash = '#/relations';
    });
    view.querySelector('#run-profiling')?.addEventListener('click', async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = '剖析中…';
      try {
        const run = await api.post('/api/model-runs', { trigger: 'manual' });
        toast(`剖析完成：${run.relation_count} 条关系 / ${run.suggestion_count} 条建议`);
        await overviewPage.render(view, ctx);
      } catch (err) {
        toast(errorMessage(err), 'err');
        button.disabled = false;
        button.textContent = '执行剖析';
      }
    });
  },
};

export default overviewPage;
