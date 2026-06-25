"""Dashboard 管理界面 — Provider 状态、模型列表、熔断器"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from openllm.server.app import registry, circuit_breaker, cooldown, health_tracker, metadata_registry, get_combos

router = APIRouter()


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenLLM Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
.header{background:linear-gradient(135deg,#1e293b,#0f172a);padding:24px 32px;border-bottom:1px solid #334155;display:flex;align-items:center;justify-content:space-between}
.header h1{font-size:24px;font-weight:700;color:#f8fafc;letter-spacing:-0.5px}
.header h1 span{color:#38bdf8;font-weight:400;margin-left:8px;font-size:14px}
.header .status-badge{padding:6px 14px;border-radius:20px;font-size:13px;font-weight:600}
.status-badge.healthy{background:#059669;color:#d1fae5}
.status-badge.degraded{background:#d97706;color:#fef3c7}
.status-badge.unhealthy{background:#dc2626;color:#fee2e2}
.header .api-link{color:#38bdf8;font-size:13px;text-decoration:none;opacity:0.8}
.header .api-link:hover{opacity:1}
.container{max-width:1200px;margin:0 auto;padding:24px 32px}
.section{margin-bottom:32px}
.section-title{font-size:18px;font-weight:600;color:#94a3b8;margin-bottom:16px;letter-spacing:-0.3px;display:flex;align-items:center;gap:8px}
.section-title .count{background:#1e293b;padding:3px 10px;border-radius:12px;font-size:12px;color:#64748b}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}
.card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;transition:border-color 0.2s}
.card:hover{border-color:#475569}
.card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.card-header .name{font-size:16px;font-weight:600;color:#f8fafc}
.card-header .state{font-size:11px;padding:4px 10px;border-radius:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px}
.state-closed{background:#059669;color:#d1fae5}
.state-open{background:#dc2626;color:#fee2e2}
.state-half_open{background:#d97706;color:#fef3c7}
.state-unknown{background:#475569;color:#cbd5e1}
.card-stats{display:flex;gap:16px}
.stat{flex:1}
.stat-label{font-size:11px;color:#64748b;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px}
.stat-value{font-size:14px;font-weight:600;color:#e2e8f0}
.stat-value.good{color:#34d399}
.stat-value.warn{color:#fbbf24}
.stat-value.bad{color:#f87171}
.score-bar{height:4px;background:#334155;border-radius:2px;margin-top:8px;overflow:hidden}
.score-fill{height:100%;border-radius:2px;transition:width 0.5s}
.models-table{width:100%;border-collapse:collapse}
.models-table th{font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;padding:10px 12px;border-bottom:1px solid #334155;text-align:left}
.models-table td{padding:10px 12px;border-bottom:1px solid #1e293b;font-size:13px;color:#cbd5e1}
.models-table tr:hover td{background:#1e293b}
.tag{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;margin-right:4px}
.tag-free{background:#059669;color:#d1fae5}
.tag-reasoning{background:#7c3aed;color:#ddd6fe}
.tag-vision{background:#2563eb;color:#dbeafe}
.tag-text{background:#475569;color:#cbd5e1}
.combo-section{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.combo-card{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px}
.combo-name{font-size:14px;font-weight:600;color:#38bdf8;margin-bottom:8px}
.combo-strategy{font-size:11px;color:#64748b;margin-bottom:10px}
.combo-members{font-size:12px;color:#94a3b8}
.combo-members span{margin-right:8px}
.combo-members .priority{color:#64748b;font-size:10px}
.endpoints{display:flex;flex-direction:column;gap:8px}
.endpoint{display:flex;align-items:center;gap:12px;padding:10px 14px;background:#1e293b;border:1px solid #334155;border-radius:8px;cursor:pointer;transition:border-color 0.2s}
.endpoint:hover{border-color:#38bdf8}
.endpoint .method{font-size:11px;font-weight:700;padding:3px 8px;border-radius:4px;min-width:40px;text-align:center}
.method-get{background:#059669;color:#d1fae5}
.method-post{background:#2563eb;color:#dbeafe}
.endpoint .path{font-size:13px;color:#f8fafc;font-family:"SF Mono",Monaco,monospace}
.endpoint .desc{font-size:12px;color:#64748b;margin-left:auto}
.loading{text-align:center;padding:40px;color:#64748b;font-size:14px}
.error-msg{text-align:center;padding:40px;color:#f87171;font-size:14px}
.empty{text-align:center;padding:30px;color:#475569;font-size:13px}
@media(max-width:640px){
  .header{padding:16px;flex-direction:column;gap:12px}
  .container{padding:16px}
  .cards{grid-template-columns:1fr}
}
</style>
</head>
<body>
<div class="header">
  <h1>OpenLLM<span>Dashboard</span></h1>
  <div style="display:flex;align-items:center;gap:16px">
    <span id="overall-badge" class="status-badge healthy">loading...</span>
    <a class="api-link" href="/docs">API Docs &rarr;</a>
  </div>
</div>

<div class="container">
  <!-- Providers -->
  <div class="section">
    <div class="section-title">Providers <span id="provider-count" class="count">0</span></div>
    <div id="providers" class="cards"><div class="loading">Loading...</div></div>
  </div>

  <!-- Models -->
  <div class="section">
    <div class="section-title">Models <span id="model-count" class="count">0</span></div>
    <div id="models-wrapper">
      <table class="models-table">
        <thead><tr><th>Model</th><th>Provider</th><th>Context</th><th>Tags</th></tr></thead>
        <tbody id="models-body"></tbody>
      </table>
    </div>
  </div>

  <!-- Combos -->
  <div class="section">
    <div class="section-title">Routing Combos <span id="combo-count" class="count">0</span></div>
    <div id="combos" class="combo-section"><div class="loading">Loading...</div></div>
  </div>

  <!-- Endpoints -->
  <div class="section">
    <div class="section-title">API Endpoints</div>
    <div class="endpoints">
      <a class="endpoint" href="/v1/models"><span class="method method-get">GET</span><span class="path">/v1/models</span><span class="desc">List models</span></a>
      <a class="endpoint" href="/v1/chat/completions"><span class="method method-post">POST</span><span class="path">/v1/chat/completions</span><span class="desc">OpenAI chat</span></a>
      <a class="endpoint" href="/v1/messages"><span class="method method-post">POST</span><span class="path">/v1/messages</span><span class="desc">Anthropic messages</span></a>
      <a class="endpoint" href="/v1/models/rankings"><span class="method method-get">GET</span><span class="path">/v1/models/rankings</span><span class="desc">Model rankings</span></a>
      <a class="endpoint" href="/health"><span class="method method-get">GET</span><span class="path">/health</span><span class="desc">Health check</span></a>
    </div>
  </div>
</div>

<script>
async function load() {
  try {
    const [health, modelsData, combosData, statusData] = await Promise.all([
      fetch('/health').then(r => r.json()),
      fetch('/v1/models').then(r => r.json()),
      fetch('/api/combos').then(r => r.json()),
      fetch('/api/status').then(r => r.json()),
    ]);

    // Overall status badge
    const badge = document.getElementById('overall-badge');
    badge.textContent = health.status === 'healthy' ? 'All Systems Normal' : health.status === 'degraded' ? 'Degraded' : 'Unhealthy';
    badge.className = 'status-badge ' + health.status;

    // Providers
    const providersEl = document.getElementById('providers');
    const providers = health.providers || {};
    const statusMap = statusData.providers || {};
    document.getElementById('provider-count').textContent = Object.keys(providers).length;
    let html = '';
    for (const [name, info] of Object.entries(providers)) {
      const st = statusMap[name] || {};
      const cbState = info.circuit_breaker?.state || 'CLOSED';
      const score = st.health_score || 100;
      const p50 = st.latency_p50 || 0;
      const failures = info.circuit_breaker?.failures || 0;
      const stateClass = cbState === 'CLOSED' ? 'closed' : cbState === 'OPEN' ? 'open' : cbState === 'HALF_OPEN' ? 'half_open' : 'unknown';
      const scoreClass = score >= 80 ? 'good' : score >= 50 ? 'warn' : 'bad';
      const scoreColor = score >= 80 ? '#34d399' : score >= 50 ? '#fbbf24' : '#f87171';
      const statusIcon = info.status === 'healthy' ? '&#10003;' : info.status === 'unreachable' ? '&#10007;' : '&#9888;';
      html += `<div class="card">
        <div class="card-header">
          <span class="name">${statusIcon} ${name}</span>
          <span class="state state-${stateClass}">${cbState}</span>
        </div>
        <div class="card-stats">
          <div class="stat"><div class="stat-label">Health</div><div class="stat-value ${scoreClass}">${score.toFixed(0)}</div></div>
          <div class="stat"><div class="stat-label">P50 Latency</div><div class="stat-value">${p50 > 0 ? p50.toFixed(0) + 'ms' : 'N/A'}</div></div>
          <div class="stat"><div class="stat-label">Failures</div><div class="stat-value ${failures > 0 ? 'bad' : ''}">${failures}</div></div>
        </div>
        <div class="score-bar"><div class="score-fill" style="width:${score}%;background:${scoreColor}"></div></div>
      </div>`;
    }
    providersEl.innerHTML = html || '<div class="empty">No providers registered</div>';

    // Models
    const models = modelsData.data || [];
    document.getElementById('model-count').textContent = models.length;
    const tbody = document.getElementById('models-body');
    if (models.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="empty">No models available</td></tr>';
    } else {
      tbody.innerHTML = models.map(m => {
        const tags = [];
        if (m.capabilities) m.capabilities.forEach(c => {
          if (c === 'free') tags.push('<span class="tag tag-free">free</span>');
          else if (c === 'reasoning') tags.push('<span class="tag tag-reasoning">reasoning</span>');
          else if (c === 'vision') tags.push('<span class="tag tag-vision">vision</span>');
          else tags.push('<span class="tag tag-text">' + c + '</span>');
        });
        if (m.supports_reasoning) tags.push('<span class="tag tag-reasoning">reasoning</span>');
        if (m.is_free) tags.push('<span class="tag tag-free">free</span>');
        return `<tr><td style="font-family:monospace;color:#f8fafc">${m.id}</td><td>${m.owned_by}</td><td>${m.context_window ? m.context_window.toLocaleString() : 'N/A'}</td><td>${tags.join('')}</td></tr>`;
      }).join('');
    }

    // Combos
    const combos = combosData.combos || {};
    document.getElementById('combo-count').textContent = Object.keys(combos).length;
    const combosEl = document.getElementById('combos');
    let comboHtml = '';
    for (const [name, cfg] of Object.entries(combos)) {
      const members = (cfg.members || []).map(m =>
        `<span>${m.provider}/${m.model} <span class="priority">P${m.priority}</span></span>`
      ).join('');
      comboHtml += `<div class="combo-card">
        <div class="combo-name">${name}</div>
        <div class="combo-strategy">${cfg.strategy}</div>
        <div class="combo-members">${members}</div>
      </div>`;
    }
    combosEl.innerHTML = comboHtml || '<div class="empty">No combos configured</div>';

  } catch (e) {
    document.getElementById('providers').innerHTML = '<div class="error-msg">Failed to load: ' + e.message + '</div>';
  }
}
load();
setInterval(load, 30000);
</script>
</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def dashboard():
    """管理界面首页"""
    return DASHBOARD_HTML


@router.get("/api/status")
async def api_status():
    """Dashboard 数据端点: Provider 详细状态 + 健康分数 + 延迟"""
    from openllm.server.app import registry as reg
    providers = reg.list_providers()
    result = {}
    for name in providers:
        cb = circuit_breaker.get_state(name)
        score = health_tracker.get_score(name)
        p50 = health_tracker.get_latency_p50(name)
        p95 = health_tracker.get_latency_p95(name)
        result[name] = {
            "health_score": score,
            "latency_p50": p50,
            "latency_p95": p95,
            "circuit_breaker": cb,
        }
    return {"providers": result}


@router.get("/api/combos")
async def api_combos():
    """Dashboard 数据端点: Combo 路由配置"""
    combos = get_combos()
    data = {}
    for name, cfg in combos.items():
        data[name] = {
            "strategy": cfg.strategy.value,
            "members": [{"provider": m.provider, "model": m.model, "priority": m.priority} for m in cfg.members],
        }
    return {"combos": data}
