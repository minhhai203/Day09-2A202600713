import { marked } from 'marked';

const PANELS = {
  overview: {
    title: 'Tổng quan Lab',
    desc: 'Tiến độ hoàn thành 7/7 phần. Chọn stage bên trái để chạy demo và xem giải thích.',
    runId: null,
    extra: 'overview',
  },
  '0': {
    title: 'Phần 0 — Chuẩn bị môi trường',
    desc: 'Python 3.11+, uv, dependencies, .env với OPENROUTER_API_KEY.',
    runId: null,
    extra: 'checklist',
    requirements: [
      'Python 3.11+, cài uv và chạy uv sync',
      'Tạo .env từ .env.example, thêm OPENROUTER_API_KEY',
      'Test Stage 1 chạy PASS trước khi sang phần sau',
    ],
  },
  '1': {
    title: 'Phần 1 — Direct LLM Calling',
    desc: 'Gọi LLM trực tiếp qua OpenRouter. SystemMessage + HumanMessage.',
    runId: '1',
    cmd: 'uv run python stages/stage_1_direct_llm/main.py',
    requirements: [
      'Hiểu get_llm() khởi tạo ChatOpenAI qua OpenRouter',
      'Ghép SystemMessage + HumanMessage thành messages list',
      'Bài 1.1: đổi QUESTION sang câu hỏi pháp lý tiếng Việt',
      'Bài 1.2: thêm temperature=0.3 trong common/llm.py',
    ],
  },
  '2': {
    title: 'Phần 2 — LLM + RAG & Tools',
    desc: 'Function calling: @tool, LEGAL_KNOWLEDGE, bind_tools().',
    runId: '2',
    cmd: 'uv run python stages/stage_2_rag_tools/main.py',
    requirements: [
      'Tìm @tool decorator, LEGAL_KNOWLEDGE và .bind_tools()',
      'Quan sát flow 3 bước: LLM → execute tool → LLM trả lời',
      'Bài 2.1: thêm entry labor_law vào LEGAL_KNOWLEDGE',
      'Bài 2.2: tạo tool check_statute_of_limitations',
    ],
  },
  '3': {
    title: 'Phần 3 — Single Agent (ReAct)',
    desc: 'create_react_agent() — agent tự lặp Think → Act → Observe.',
    runId: '3',
    cmd: 'uv run python stages/stage_3_single_agent/main.py',
    requirements: [
      'Quan sát agent tự gọi nhiều tools (search, compliance, penalty…)',
      'So sánh với Stage 2: không còn viết tool loop thủ công',
      'Bài 3.1: thêm tool search_case_law',
      'Bài 3.2: debug reasoning với astream(debug=True)',
    ],
  },
  '4': {
    title: 'Phần 4 — Multi-Agent In-Process',
    desc: 'LangGraph StateGraph, Send() API, parallel specialists.',
    runId: '4',
    cmd: 'uv run python stages/stage_4_milti_agent/main.py',
    requirements: [
      'Phân tích LegalState, nodes và Send() API',
      'Luồng: analyze_law → routing → [tax ∥ compliance ∥ privacy] → aggregate',
      'Bài 4.1: thêm call_privacy_specialist',
      'Bài 4.2: keyword routing cho data/privacy/gdpr',
    ],
  },
  '5': {
    title: 'Phần 5 — Distributed A2A System',
    desc: '5 services: Registry + 4 agents. Khởi động services trước, rồi chạy test client.',
    runId: '5-test',
    isDistributed: true,
    cmd: 'uv run python test_client.py',
    requirements: [
      'Khởi động 5 services: Registry (:10000) + 4 agents',
      'Chạy test_client.py E2E — quan sát trace_id qua các hop',
      'Bài 5.1: trace request flow qua Customer → Law → Tax/Compliance',
      'Bài 5.2: dừng Tax Agent, test lại hành vi hệ thống',
    ],
  },
  '6': {
    title: 'Phần 6 — Tổng kết & Bài cộng điểm',
    desc: 'Latency baseline vs optimized. Câu hỏi ôn tập và trade-offs.',
    runId: null,
    requirements: [
      'Trả lời: single vs multi-agent, A2A vs REST, prevent infinite loops',
      'Đo latency baseline (~150s) và sau tối ưu (~45s)',
      'Bật LATENCY_OPTIMIZED=1 và LLM_MAX_TOKENS=350 khi benchmark',
    ],
  },
  ex2: {
    title: 'Exercise 2 — Tools & Knowledge Base',
    desc: 'Thêm labor_law entry và tool check_statute_of_limitations.',
    runId: 'ex2',
    cmd: 'uv run python exercises/exercise_2_tools.py',
    requirements: [
      'Thêm entry labor_law vào LEGAL_KNOWLEDGE',
      'Implement tool check_statute_of_limitations(case_type)',
      'Test với câu hỏi về thời hiệu khởi kiện — output không lỗi',
    ],
  },
  ex4: {
    title: 'Exercise 4 — Privacy Agent',
    desc: 'Thêm privacy specialist vào multi-agent graph.',
    runId: 'ex4',
    cmd: 'uv run python exercises/exercise_4_multiagent.py',
    requirements: [
      'Implement privacy_agent function xử lý data breach/GDPR',
      'Thêm routing keyword: data, privacy, gdpr, dữ liệu',
      'Thêm node vào graph, test 3 agents chạy song song',
    ],
  },
};

let sections = {};
let activePanel = 'overview';
let eventSources = {};
let traceEventSource = null;
let traceStepsSeen = new Set();
let servicePollTimer = null;

// ── Tab switching ──
document.getElementById('sidebar').addEventListener('click', (e) => {
  const btn = e.target.closest('.tab-btn');
  if (!btn) return;
  switchPanel(btn.dataset.panel);
});

function switchPanel(id) {
  activePanel = id;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.panel === id));
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.dataset.panel === id));
  if (id === '5') startServicePolling();
  else stopServicePolling();
  if (id !== '5') stopTraceStream();
}

// ── Build panels ──
function buildPanels() {
  const main = document.getElementById('main-content');
  main.innerHTML = '';

  for (const [id, cfg] of Object.entries(PANELS)) {
    const panel = document.createElement('div');
    panel.className = 'panel' + (id === activePanel ? ' active' : '');
    panel.dataset.panel = id;

    let actionHtml = '';
    if (cfg.isDistributed) {
      actionHtml = `
        <div class="service-grid" id="services-${id}"></div>
        <div class="env-options">
          <label class="env-toggle" title="Bật trước khi khởi động services">
            <input type="checkbox" id="latency-opt-toggle" onchange="saveLatencyPref()" />
            <span class="env-switch"></span>
            <span class="env-toggle-label">
              <strong>⚡ Tối ưu latency</strong>
              <span>LATENCY_OPTIMIZED=1 · LLM_MAX_TOKENS=350</span>
            </span>
          </label>
          <span class="env-hint" id="latency-opt-hint">Tắt = baseline (~150s). Bật = optimized (~45s). Chọn trước khi nhấn Khởi động Services.</span>
        </div>
        <div class="action-bar">
          <button class="btn btn-primary" onclick="startServices()">▶ Khởi động Services</button>
          <button class="btn btn-primary" onclick="runStage('${id}')" id="run-btn-${id}">▶ Chạy Test Client</button>
          <button class="btn btn-danger" onclick="stopServices()">⏹ Dừng Services</button>
          <span class="status-pill" id="status-${id}"><span class="status-dot"></span> Sẵn sàng</span>
        </div>`;
    } else if (cfg.runId) {
      actionHtml = `
        <div class="action-bar">
          <button class="btn btn-primary" onclick="runStage('${id}')" id="run-btn-${id}">▶ Chạy</button>
          <code style="font-size:12px;color:var(--muted)">${cfg.cmd || ''}</code>
          <span class="status-pill" id="status-${id}"><span class="status-dot"></span> Sẵn sàng</span>
        </div>`;
    }

    const hasTerminal = cfg.runId || cfg.isDistributed;
    panel.innerHTML = `
      <div class="panel-header">
        <h2>${cfg.title}</h2>
        <p>${cfg.desc}</p>
      </div>
      ${!hasTerminal ? requirementsHtml(id, true) : ''}
      ${actionHtml}
      ${hasTerminal ? terminalHtml(id) : ''}
      ${cfg.extra === 'checklist' ? checklistHtml() : learnSectionHtml(id)}
    `;
    main.appendChild(panel);
  }
}

function requirementsHtml(id, standalone = false) {
  const reqs = PANELS[id]?.requirements;
  if (!reqs?.length) return '';
  const items = reqs.map(r => `<li>${escapeHtml(r)}</li>`).join('');
  const cls = standalone ? 'stage-requirements standalone' : 'stage-requirements';
  return `<div class="${cls}"><strong>📋 Yêu cầu stage</strong><ul>${items}</ul></div>`;
}

function traceFlowHtml(id) {
  return `
    <div class="trace-flow-wrap">
      <div class="trace-flow-header">
        <strong>🔗 A2A Request Trace</strong>
        <span class="trace-id-badge" id="trace-id-${id}" title="Trace ID">—</span>
      </div>
      <div id="trace-warning-${id}"></div>
      <div class="trace-call-graph" id="trace-graph-${id}"></div>
      <div class="trace-steps" id="trace-steps-${id}"></div>
      <div class="trace-summary-wrap" id="trace-summary-${id}"></div>
    </div>`;
}

function terminalHtml(id) {
  const tracePanel = PANELS[id]?.isDistributed ? traceFlowHtml(id) : '';
  return `
    ${tracePanel}
    <div class="terminal-wrap">
      <div class="terminal-bar">
        <div class="title">
          <div class="terminal-dots"><span></span><span></span><span></span></div>
          Output — ${PANELS[id].title}
        </div>
        <div class="terminal-actions">
          <button class="btn btn-secondary btn-sm" onclick="clearLog('${id}')">Clear</button>
          <button class="btn btn-secondary btn-sm" onclick="copyLog('${id}')">Copy</button>
          <button class="btn btn-secondary btn-sm" onclick="toggleAutoScroll('${id}')" id="autoscroll-${id}">Auto-scroll: ON</button>
        </div>
      </div>
      ${requirementsHtml(id)}
      <div class="terminal-body" id="log-${id}"></div>
    </div>`;
}

function learnSectionHtml(id) {
  if (id === 'overview') {
    return `<div class="learn-section open" id="learn-${id}">
      <div class="learn-header" onclick="toggleLearn('${id}')">
        <h3>📖 Tiến độ & Lệnh chạy nhanh</h3>
        <span class="chevron">▼</span>
      </div>
      <div class="learn-body" id="learn-body-${id}"></div>
    </div>`;
  }
  return `<div class="learn-section" id="learn-${id}">
    <div class="learn-header" onclick="toggleLearn('${id}')">
      <h3>📖 Học tập — Câu hỏi & Giải thích</h3>
      <span class="chevron">▼</span>
    </div>
    <div class="learn-body" id="learn-body-${id}"></div>
  </div>`;
}

function checklistHtml() {
  return `<div class="learn-section open">
    <div class="learn-header" onclick="toggleLearn('0')">
      <h3>✅ Checklist chuẩn bị</h3>
      <span class="chevron">▼</span>
    </div>
    <div class="learn-body" id="learn-body-0"></div>
  </div>`;
}

function toggleLearn(id) {
  document.getElementById(`learn-${id}`)?.classList.toggle('open');
}

// ── Log rendering ──
const autoScroll = {};

function classifyLine(line) {
  if (/^\[TRACE\]/i.test(line)) return 'log-trace';
  if (/PASS|✅|success|Success|OK/i.test(line)) return 'log-success';
  if (/error|Error|FAIL|❌|Traceback|Exception/i.test(line)) return 'log-error';
  if (/warn|Warn|⚠|deprecated/i.test(line)) return 'log-warning';
  if (/^Step \d|→|Latency|⏱|Connecting|Question:|Câu hỏi:/i.test(line)) return 'log-info';
  if (/^#{1,3} |^---|^\*{3,}/.test(line)) return 'log-accent';
  if (/^[-=]{10,}/.test(line)) return 'log-divider';
  if (/^\s*[\[{]/.test(line) || /tool_calls|Reasoning/i.test(line)) return 'log-highlight';
  return '';
}

function appendLog(panelId, line, isStart = false) {
  const el = document.getElementById(`log-${panelId}`);
  if (!el) return;

  const ts = new Date().toLocaleTimeString('vi-VN', { hour12: false });
  const cls = classifyLine(line);
  const div = document.createElement('span');
  div.className = 'log-line' + (cls ? ' ' + cls : '');
  div.innerHTML = `<span class="log-ts">${ts}</span>${escapeHtml(line)}`;
  el.appendChild(div);
  el.appendChild(document.createTextNode('\n'));

  if (autoScroll[panelId] !== false) {
    el.scrollTop = el.scrollHeight;
  }
}

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function clearLog(id) {
  const el = document.getElementById(`log-${id}`);
  if (el) el.innerHTML = '';
  if (id === '5') clearTraceFlow('5');
}

function clearTraceFlow(panelId) {
  const steps = document.getElementById(`trace-steps-${panelId}`);
  const badge = document.getElementById(`trace-id-${panelId}`);
  const graph = document.getElementById(`trace-graph-${panelId}`);
  const summary = document.getElementById(`trace-summary-${panelId}`);
  const warning = document.getElementById(`trace-warning-${panelId}`);
  if (steps) steps.innerHTML = '';
  if (graph) graph.innerHTML = '';
  if (summary) summary.innerHTML = '';
  if (warning) warning.innerHTML = '';
  if (badge) { badge.textContent = '—'; badge.title = 'Trace ID'; }
  traceStepsSeen = new Set();
}

function renderCallGraph(summary) {
  const hops = summary?.call_chain || [];
  if (!hops.length) {
    return 'Test Client ──A2A──▶ Customer (:10100) ──A2A──▶ Law (:10101)\n'
      + '                              ├─▶ Tax (:10102)\n'
      + '                              └─▶ Compliance (:10103)   [chưa có dữ liệu]';
  }

  const lines = [];
  for (const hop of hops) {
    const src = SERVICE_LABELS[hop.from] || hop.from;
    const dst = SERVICE_LABELS[hop.to] || hop.to;
    const port = SERVICE_PORTS[hop.to];
    const portStr = port ? ` (:${port})` : '';
    lines.push(`${src} ──A2A──▶ ${dst}${portStr}  [depth=${hop.depth ?? '?'}]`);
  }

  const routing = summary.routing;
  if (routing) {
    lines.push('');
    lines.push(`Law routing: tax=${routing.needs_tax} · compliance=${routing.needs_compliance}`);
  }
  if (summary.graph_nodes?.length) {
    lines.push(`Law graph: ${summary.graph_nodes.join(' → ')}`);
  }
  if (summary.latency_s != null) {
    lines.push(`Latency: ${summary.latency_s}s · ${summary.event_count ?? 0} events`);
  }
  return lines.join('\n');
}

function renderAgentSummary(summary) {
  const results = summary?.agent_results || [];
  if (!results.length) {
    return '<p style="color:var(--muted);font-size:12px;margin:0">Chưa có kết quả từ agents.</p>';
  }
  return results.map(r => {
    const name = SERVICE_LABELS[r.service] || r.service;
    const prev = r.preview || '(không có preview)';
    return `<div class="trace-result-card">
      <div class="agent-name">${escapeHtml(name)} · ${r.chars ?? 0} chars</div>
      <div class="agent-preview">${escapeHtml(prev)}</div>
    </div>`;
  }).join('');
}

function renderFullTrace(panelId, events, summary) {
  clearTraceFlow(panelId);

  const badge = document.getElementById(`trace-id-${panelId}`);
  if (badge && summary?.trace_id) {
    badge.textContent = summary.trace_id;
    badge.title = summary.trace_id;
  }

  const warningEl = document.getElementById(`trace-warning-${panelId}`);
  if (warningEl && summary?.warning) {
    warningEl.className = 'trace-warning';
    warningEl.textContent = '⚠️ ' + summary.warning;
  }

  const graphEl = document.getElementById(`trace-graph-${panelId}`);
  if (graphEl) graphEl.textContent = renderCallGraph(summary);

  const summaryEl = document.getElementById(`trace-summary-${panelId}`);
  if (summaryEl) {
    summaryEl.innerHTML = `<h4>📋 Kết quả tóm tắt từng Agent</h4>${renderAgentSummary(summary)}`;
  }

  for (const evt of events) {
    appendTraceEvent(panelId, evt, true);
  }
}

async function refreshTracePanel(panelId) {
  try {
    const res = await fetch('/api/trace/events');
    const data = await res.json();
    renderFullTrace(panelId, data.events || [], data.summary || {});
  } catch (_) {}
}

const SERVICE_LABELS = {
  test_client: 'Test Client',
  customer: 'Customer Agent',
  law: 'Law Agent',
  tax: 'Tax Agent',
  compliance: 'Compliance Agent',
  registry: 'Registry',
};

const SERVICE_PORTS = { customer: 10100, law: 10101, tax: 10102, compliance: 10103 };

function formatTraceStep(evt) {
  const svc = SERVICE_LABELS[evt.service] || evt.service;
  const port = evt.port || SERVICE_PORTS[evt.service];
  const portStr = port ? ` :${port}` : '';

  switch (evt.event) {
    case 'request_start':
      return { cls: 'hop', icon: '①', title: `${svc} → Customer Agent${portStr ? ' (:10100)' : ''}`, meta: `trace=${evt.trace_id?.slice(0, 8)}… depth=${evt.depth ?? 0}` };
    case 'agent_receive':
      return { cls: 'hop', icon: '●', title: `${svc} nhận request`, meta: `depth=${evt.depth ?? '?'} · task=${evt.task_id?.slice(0, 8) ?? '—'}…` };
    case 'a2a_send': {
      const to = SERVICE_LABELS[evt.to] || evt.to;
      const toPort = SERVICE_PORTS[evt.to] ? ` (:${SERVICE_PORTS[evt.to]})` : '';
      return { cls: 'hop', icon: '→', title: `${svc} → ${to}${toPort} (A2A)`, meta: `depth=${evt.depth ?? '?'} · HTTP POST message/send` };
    }
    case 'a2a_recv': {
      const from = SERVICE_LABELS[evt.from_agent] || evt.from_agent;
      return {
        cls: 'hop', icon: '←', title: `${from} trả lời về ${svc}`,
        meta: `${evt.chars ?? 0} chars · depth=${evt.depth ?? '?'}`,
        preview: evt.preview || '',
      };
    }
    case 'graph_node':
      return { cls: 'node', icon: '◆', title: `${svc}: node "${evt.node}"`, meta: `LangGraph in-process` };
    case 'routing':
      return { cls: 'node', icon: '⑂', title: `${svc} routing decision`, meta: `needs_tax=${evt.needs_tax} · needs_compliance=${evt.needs_compliance}` };
    case 'parallel_dispatch':
      return { cls: 'parallel', icon: '∥', title: `${svc} dispatch song song`, meta: (evt.targets || []).map(t => SERVICE_LABELS[t] || t).join('  ∥  ') };
    case 'agent_complete':
      return {
        cls: 'done', icon: '✓', title: `${svc} hoàn thành`,
        meta: `${evt.chars ?? 0} chars · depth=${evt.depth ?? '?'}`,
        preview: evt.preview || '',
      };
    case 'request_complete':
      return { cls: 'done', icon: '✓', title: 'E2E request hoàn tất', meta: `latency=${evt.latency_s}s` };
    default:
      return { cls: '', icon: '·', title: `${evt.event} @ ${svc}`, meta: JSON.stringify(evt).slice(0, 80) };
  }
}

function appendTraceEvent(panelId, evt, skipDedup = false) {
  if (!evt?.trace_id || !evt?.event) return;

  const key = `${evt.ts ?? ''}:${evt.event}:${evt.service}:${evt.node || ''}:${evt.to || ''}:${evt.from_agent || ''}:${evt.depth ?? ''}`;
  if (!skipDedup && traceStepsSeen.has(key)) return;
  traceStepsSeen.add(key);

  const badge = document.getElementById(`trace-id-${panelId}`);
  if (badge) {
    badge.textContent = evt.trace_id;
    badge.title = evt.trace_id;
  }

  const steps = document.getElementById(`trace-steps-${panelId}`);
  if (!steps) return;

  const { cls, icon, title, meta, preview } = formatTraceStep(evt);
  const previewHtml = preview
    ? `<div class="step-preview">${escapeHtml(preview)}</div>` : '';
  const div = document.createElement('div');
  div.className = `trace-step ${cls}`;
  div.innerHTML = `<span class="step-icon">${icon}</span><div class="step-body"><div class="step-title">${escapeHtml(title)}</div><div class="step-meta">${escapeHtml(meta)}</div>${previewHtml}</div>`;
  steps.appendChild(div);
  steps.scrollTop = steps.scrollHeight;
}

function parseTraceFromLogLine(line) {
  const m = line.match(/^\[TRACE\]\s*(\{.*\})\s*$/);
  if (!m) return null;
  try { return JSON.parse(m[1]); } catch { return null; }
}

function startTraceStream(panelId) {
  stopTraceStream();
  clearTraceFlow(panelId);
  traceEventSource = new EventSource('/api/trace/stream');
  traceEventSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === 'trace' && data.event) {
      appendTraceEvent(panelId, data.event);
    }
  };
  traceEventSource.onerror = () => stopTraceStream();
}

function stopTraceStream() {
  if (traceEventSource) {
    traceEventSource.close();
    traceEventSource = null;
  }
}

function copyLog(id) {
  const el = document.getElementById(`log-${id}`);
  if (!el) return;
  navigator.clipboard.writeText(el.textContent);
}

function toggleAutoScroll(id) {
  autoScroll[id] = autoScroll[id] === false;
  const btn = document.getElementById(`autoscroll-${id}`);
  if (btn) btn.textContent = `Auto-scroll: ${autoScroll[id] === false ? 'OFF' : 'ON'}`;
}

function setStatus(panelId, state, text) {
  const el = document.getElementById(`status-${panelId}`);
  if (!el) return;
  el.className = 'status-pill ' + state;
  el.innerHTML = `<span class="status-dot"></span> ${text}`;
}

function setRunDisabled(panelId, disabled) {
  const btn = document.getElementById(`run-btn-${panelId}`);
  if (btn) btn.disabled = disabled;
}

// ── Run stage via SSE ──
function runStage(panelId) {
  const cfg = PANELS[panelId];
  if (!cfg?.runId) return;

  if (eventSources[panelId]) {
    eventSources[panelId].close();
  }

  clearLog(panelId);
  autoScroll[panelId] = true;
  setStatus(panelId, 'running', 'Đang chạy…');
  setRunDisabled(panelId, true);

  if (panelId === '5') {
    fetch('/api/trace/clear', { method: 'POST' }).catch(() => {});
    startTraceStream(panelId);
  }

  const es = new EventSource(`/api/run/${cfg.runId}`);
  eventSources[panelId] = es;

  es.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === 'start') {
      appendLog(panelId, `$ ${data.cmd}`);
      appendLog(panelId, '─'.repeat(60));
    } else if (data.type === 'log') {
      appendLog(panelId, data.line);
      const traceEvt = parseTraceFromLogLine(data.line);
      if (traceEvt) appendTraceEvent(panelId, traceEvt);
    } else if (data.type === 'done') {
      const ok = data.status === 'success';
      setStatus(panelId, ok ? 'success' : 'error', ok ? `Hoàn thành (exit ${data.code})` : `Lỗi (exit ${data.code})`);
      setRunDisabled(panelId, false);
      es.close();
      delete eventSources[panelId];
      if (panelId === '5') {
        stopTraceStream();
        setTimeout(() => refreshTracePanel(panelId), 400);
      }
    } else if (data.type === 'error') {
      appendLog(panelId, data.line);
    }
  };

  es.onerror = () => {
    setStatus(panelId, 'error', 'Mất kết nối SSE');
    setRunDisabled(panelId, false);
    es.close();
  };
}

// ── Stage 5 services ──
function isLatencyOptimized() {
  return document.getElementById('latency-opt-toggle')?.checked ?? false;
}

function saveLatencyPref() {
  localStorage.setItem('lab-latency-opt', isLatencyOptimized() ? '1' : '0');
  updateLatencyHint();
}

function updateLatencyHint() {
  const hint = document.getElementById('latency-opt-hint');
  if (!hint) return;
  hint.textContent = isLatencyOptimized()
    ? '✅ Sẽ export LATENCY_OPTIMIZED=1 và LLM_MAX_TOKENS=350 khi khởi động (~45s)'
    : '📊 Baseline — không set env tối ưu (~150s). Bật toggle nếu muốn chạy nhanh.';
}

function initLatencyPref() {
  const saved = localStorage.getItem('lab-latency-opt');
  const toggle = document.getElementById('latency-opt-toggle');
  if (toggle && saved !== null) toggle.checked = saved === '1';
  updateLatencyHint();
}

async function startServices() {
  const optimized = isLatencyOptimized();
  setStatus('5', 'running', 'Đang khởi động services…');
  appendLog('5', optimized
    ? '⚡ Env: LATENCY_OPTIMIZED=1, LLM_MAX_TOKENS=350'
    : '📊 Env: baseline (unset LATENCY_OPTIMIZED, LLM_MAX_TOKENS)');
  const res = await fetch('/api/services/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ latency_optimized: optimized }),
  });
  const data = await res.json();
  appendLog('5', `🚀 ${data.message || data.status}`);
  if (data.pid) appendLog('5', `PID: ${data.pid}`);
  setTimeout(refreshServices, 3000);
}

async function stopServices() {
  const res = await fetch('/api/services/stop', { method: 'POST' });
  const data = await res.json();
  appendLog('5', `⏹ Đã dừng: ${data.killed.join(', ')}`);
  setStatus('5', '', 'Sẵn sàng');
  refreshServices();
}

async function refreshServices() {
  try {
    const res = await fetch('/api/services/status');
    const data = await res.json();
    const grid = document.getElementById('services-5');
    if (!grid) return;

    const labels = { registry: 'Registry', customer: 'Customer', law: 'Law', tax: 'Tax', compliance: 'Compliance' };
    const ports = { registry: 10000, customer: 10100, law: 10101, tax: 10102, compliance: 10103 };

    grid.innerHTML = Object.entries(labels).map(([key, name]) => {
      const up = data.ports[key];
      return `<div class="service-card ${up ? 'up' : 'down'}">
        <div class="name">${name} <span class="indicator">${up ? '●' : '○'}</span></div>
        <div class="port">:${ports[key]}</div>
      </div>`;
    }).join('');

    if (data.all_up) setStatus('5', 'success', 'Tất cả services đang chạy');
  } catch (_) {}
}

function startServicePolling() {
  refreshServices();
  servicePollTimer = setInterval(refreshServices, 5000);
}

function stopServicePolling() {
  if (servicePollTimer) { clearInterval(servicePollTimer); servicePollTimer = null; }
}

// ── Load markdown content ──
async function loadContent() {
  const res = await fetch('/api/sections');
  const data = await res.json();
  sections = data.sections;
  document.getElementById('project-root').textContent = data.root;

  if (sections.overview) {
    const el = document.getElementById('learn-body-overview');
    if (el) el.innerHTML = marked.parse(sections.overview);
  }

  const learnMap = { '0':'0', '1':'1', '2':'2', '3':'3', '4':'4', '5':'5', '6':'6', ex2:'2', ex4:'4' };
  for (const [panelId, sectionKey] of Object.entries(learnMap)) {
    const el = document.getElementById(`learn-body-${panelId}`);
    if (el && sections[sectionKey]) {
      el.innerHTML = marked.parse(sections[sectionKey]);
    }
  }
}

// ── Theme toggle ──
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const isDark = theme === 'dark';
  document.getElementById('theme-icon').textContent = isDark ? '🌙' : '☀️';
  document.getElementById('theme-label').textContent = isDark ? 'Tối' : 'Sáng';
  localStorage.setItem('lab-theme', theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  applyTheme(current === 'dark' ? 'light' : 'dark');
}

function initTheme() {
  const saved = localStorage.getItem('lab-theme');
  const prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches;
  applyTheme(saved || (prefersLight ? 'light' : 'dark'));
}

// ── Init ──
initTheme();
buildPanels();
initLatencyPref();
loadContent();
autoScroll['1'] = autoScroll['2'] = autoScroll['3'] = autoScroll['4'] = autoScroll['5'] = true;
autoScroll['ex2'] = autoScroll['ex4'] = true;
// Expose globals for onclick handlers in dynamic HTML
Object.assign(window, {
  toggleTheme, runStage, startServices, stopServices,
  clearLog, copyLog, toggleAutoScroll, toggleLearn, saveLatencyPref,
});
