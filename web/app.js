/**
 * Agentic AI Framework • Localhost Studio & Animated Control Center
 * Real-time SSE streaming, Animated Pipeline Engine, Web HITL, and Code Inspector.
 */

// Application State
let selectedMode = 'run';
let activeJobId = null;
let eventSource = null;
let timerInterval = null;
let activeHitlReqId = null;
let totalToolsInvoked = 0;
let eventsReceivedCount = 0;
let currentViewMode = 'flow';

// ==============================================================================
// 1. Tab & View Mode Switching
// ==============================================================================

function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

  const targetBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b =>
    b.getAttribute('onclick')?.includes(tabId)
  );
  if (targetBtn) targetBtn.classList.add('active');

  const content = document.getElementById('tab-' + tabId);
  if (content) content.classList.add('active');

  if (tabId === 'files') refreshFileTree();
  if (tabId === 'telemetry') loadTelemetry();
}

function setViewMode(mode) {
  currentViewMode = mode;
  document.querySelectorAll('.view-pill').forEach(p => p.classList.remove('active'));
  const activePill = Array.from(document.querySelectorAll('.view-pill')).find(p =>
    p.getAttribute('onclick')?.includes(mode)
  );
  if (activePill) activePill.classList.add('active');

  const splitView = document.getElementById('contentSplitView');
  const canvas = document.getElementById('flowCanvasContainer');
  const timeline = document.getElementById('timelineContainer');
  const terminal = document.getElementById('terminalContainer');

  if (mode === 'flow') {
    canvas.style.display = 'block';
    timeline.style.display = 'flex';
    terminal.style.display = 'none';
    splitView.classList.remove('split-active');
  } else if (mode === 'console') {
    canvas.style.display = 'none';
    timeline.style.display = 'none';
    terminal.style.display = 'flex';
    splitView.classList.remove('split-active');
  } else if (mode === 'split') {
    canvas.style.display = 'block';
    timeline.style.display = 'flex';
    terminal.style.display = 'flex';
    splitView.classList.add('split-active');
  }
}

// Mode Selection
function selectMode(mode, element) {
  selectedMode = mode;
  document.querySelectorAll('.mode-card').forEach(c => c.classList.remove('selected'));
  element.classList.add('selected');
}

// Preset Quick Chips
function applyPreset(text, mode, file) {
  document.getElementById('taskInput').value = text;
  if (file) document.getElementById('targetFileInput').value = file;

  const card = Array.from(document.querySelectorAll('.mode-card')).find(c =>
    c.getAttribute('onclick')?.includes(mode)
  );
  if (card) selectMode(mode, card);
}

// ==============================================================================
// 2. Animated Pipeline Controller
// ==============================================================================

const PIPELINE_NODES = ['input', 'planner', 'agent', 'tools', 'hitl', 'regression', 'output'];

function resetPipeline() {
  PIPELINE_NODES.forEach((name, idx) => {
    const node = document.getElementById(`pnode-${name}`);
    const badge = document.getElementById(`pbadge-${name}`);
    if (node) {
      node.className = 'pipe-node idle';
    }
    if (badge) {
      badge.textContent = name === 'input' ? 'Active' : 'Waiting';
      badge.className = 'pipe-node-badge';
    }
    if (idx > 0) {
      const cable = document.getElementById(`pcable-${idx}`);
      if (cable) cable.className = 'pipe-cable';
    }
  });

  // Reset counters
  totalToolsInvoked = 0;
  eventsReceivedCount = 0;
  document.getElementById('hudToolsCount').textContent = '0';
  document.getElementById('eventsCountBadge').textContent = '0 events';
  document.getElementById('actionTimelineList').innerHTML = '';
}

function setPipelineNodeState(nodeKey, state, badgeText, cableIdx = null) {
  const node = document.getElementById(`pnode-${nodeKey}`);
  const badge = document.getElementById(`pbadge-${nodeKey}`);

  if (node) {
    node.className = `pipe-node ${state}`;
  }
  if (badge && badgeText) {
    badge.textContent = badgeText;
  }
  if (cableIdx) {
    const cable = document.getElementById(`pcable-${cableIdx}`);
    if (cable) {
      cable.className = `pipe-cable ${state}`;
    }
  }
}

function updateHUD(icon, agent, statePill, desc) {
  if (icon) document.getElementById('holoCoreIcon').textContent = icon;
  if (agent) document.getElementById('hudActiveAgent').textContent = agent;
  if (statePill) {
    const pill = document.getElementById('hudStatePill');
    pill.textContent = statePill.toUpperCase();
    if (statePill === 'running' || statePill === 'thinking' || statePill === 'tool') {
      pill.className = 'tag running';
    } else if (statePill === 'approval') {
      pill.className = 'tag failed';
    } else if (statePill === 'done') {
      pill.className = 'tag success';
    }
  }
  if (desc) document.getElementById('hudStatusDesc').textContent = desc;
}

// ==============================================================================
// 3. Workflow Launch & Execution
// ==============================================================================

async function launchWorkflow() {
  const task = document.getElementById('taskInput').value.trim();
  const targetDir = document.getElementById('targetDirInput').value.trim();
  const targetFile = document.getElementById('targetFileInput').value.trim();
  const provider = document.getElementById('providerSelect').value;
  const model = document.getElementById('modelInput').value.trim();
  const hitl = document.getElementById('hitlToggle').checked;

  if (!task) {
    alert('Please enter a task description.');
    return;
  }

  const btn = document.getElementById('runWorkflowBtn');
  btn.disabled = true;
  btn.innerHTML = '<span>⏳</span> Initializing Multi-Agent Engine...';

  try {
    const resp = await fetch('/api/workflow/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode: selectedMode,
        task: task,
        target_dir: targetDir,
        file: targetFile,
        hitl: hitl,
        provider: provider,
        model: model,
      }),
    });

    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.detail || 'Failed to start workflow');
    }

    activeJobId = data.job_id;

    // Reset Live Studio UI & Visual Pipeline
    resetPipeline();
    clearTerminal();
    document.getElementById('summaryCard').style.display = 'none';
    document.getElementById('hitlAlertCard').style.display = 'none';

    document.getElementById('liveTaskTitle').textContent = task;
    document.getElementById('liveTaskSub').textContent = `Target: ${targetDir} • Mode: ${selectedMode.toUpperCase()} • Provider: ${provider}`;
    document.getElementById('liveStatusBadge').className = 'tag running';
    document.getElementById('liveStatusBadge').textContent = 'RUNNING';

    document.getElementById('headerPulse').className = 'pulse-dot running';
    document.getElementById('headerStatusText').textContent = 'Engine Active';

    // Step 1: Input & Safety Node Active
    setPipelineNodeState('input', 'active', 'Sanitizing...', null);
    updateHUD('🎯', 'Input Guardrail', 'running', 'Verifying safety guardrails, redacting secrets & checking prompt armor...');

    startTimer();
    switchTab('studio');

    // Smooth transition to planner
    setTimeout(() => {
      setPipelineNodeState('input', 'completed', 'Verified ✓', 1);
      setPipelineNodeState('planner', 'active', 'Decomposing...', 2);
      updateHUD('🧠', 'Task Planner', 'planning', 'Decomposing task and retrieving semantic codebase context...');
    }, 700);

  } catch (err) {
    alert('Error launching agent: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>🚀</span> Launch Agent Workflow';
  }
}

// ==============================================================================
// 4. Real-Time Event Stream (SSE) & Animated Dispatcher
// ==============================================================================

function connectSSE() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource('/api/workflow/events');

  eventSource.addEventListener('message', (e) => {
    try {
      const ev = JSON.parse(e.data);
      handleLiveEvent(ev);
    } catch (err) {}
  });

  eventSource.addEventListener('error', () => {
    // Reconnect handled automatically by browser EventSource
  });
}

function handleLiveEvent(ev) {
  eventsReceivedCount++;
  document.getElementById('eventsCountBadge').textContent = `${eventsReceivedCount} events`;

  const type = ev.type;
  const timeStr = new Date().toLocaleTimeString();

  // 1. Process Event for Visual Pipeline & HUD
  if (type === 'agent_start') {
    const agentName = ev.agent || 'SpecialistAgent';
    document.getElementById('pnodeAgentTitle').textContent = agentName;
    document.getElementById('pnodeAgentSub').textContent = ev.task?.slice(0, 25) || 'Active';

    setPipelineNodeState('planner', 'completed', 'Planned ✓', 2);
    setPipelineNodeState('agent', 'active', 'Thinking...', 3);
    updateHUD('🤖', agentName, 'running', `Specialist agent activated: ${ev.task}`);

  } else if (type === 'thought') {
    updateHUD('💭', null, 'thinking', ev.thought?.slice(0, 90) + '...');
    addTimelineEvent('thought', 'Reasoning Step', ev.thought, '🧠');

  } else if (type === 'tool_call') {
    totalToolsInvoked++;
    document.getElementById('hudToolsCount').textContent = String(totalToolsInvoked);

    setPipelineNodeState('agent', 'active', 'Calling Tool', 3);
    setPipelineNodeState('tools', 'active', ev.tool, 4);

    const toolDetail = ev.detail ? ` (${ev.detail})` : '';
    updateHUD('⚡', null, 'tool', `Executing MCP Tool: ${ev.tool}${toolDetail}`);
    addTimelineEvent('tool', `Tool: ${ev.tool}`, ev.detail || 'Tool invocation executed', '⚡');

  } else if (type === 'diff') {
    setPipelineNodeState('tools', 'completed', 'Modified ✓', 4);
    updateHUD('📝', null, 'patch', `Formulated code patch for ${ev.file_path}`);
    addTimelineEvent('diff', `Code Patch: ${ev.file_path}`, ev.diff, '📝', true);

  } else if (type === 'hitl_request') {
    setPipelineNodeState('hitl', 'active', 'APPROVAL REQ', 5);
    updateHUD('⚠️', 'Human Gatekeeper', 'approval', `Paused: Awaiting your approval on ${ev.action_name}`);
    showHitlModal(ev);
    addTimelineEvent('hitl', `Approval Required: ${ev.action_name}`, ev.details, '⚠️');

  } else if (type === 'hitl_resolved') {
    hideHitlModal();
    const statusText = ev.approved ? 'Approved ✓' : 'Rejected ✗';
    setPipelineNodeState('hitl', ev.approved ? 'completed' : 'failed', statusText, 5);
    updateHUD(ev.approved ? '✅' : '❌', null, 'running', `Human decision received: ${statusText}`);
    addTimelineEvent(ev.approved ? 'success' : 'hitl', `Human Decision: ${statusText}`, ev.feedback || 'User approved modification', '🛡️');

  } else if (type === 'regression_gate') {
    if (ev.status === 'skipped') {
      setPipelineNodeState('regression', 'skipped', 'Skipped (High Conf)', 6);
      updateHUD('⚡', 'Regression Gate', 'running', 'Smart gate: Regression check skipped (minor edit with high confidence)');
      addTimelineEvent('success', 'Regression Gate Skipped', ev.reason || 'Confidence high; zero risk detected.', '⚡');
    } else {
      setPipelineNodeState('regression', 'active', 'Testing...', 6);
      updateHUD('🧪', 'Regression Test Agent', 'running', 'Executing pytest regression test suite to ensure zero regressions...');
      addTimelineEvent('tool', 'Running Pytest Regression', 'Testing targeted modified components...', '🧪');
    }

  } else if (type === 'workflow_completed') {
    stopTimer();
    const status = ev.status || 'success';

    if (status === 'success' || status === 'completed') {
      setPipelineNodeState('regression', 'completed', 'Passed ✓', 6);
      setPipelineNodeState('output', 'completed', 'Verified ✨', null);

      document.getElementById('liveStatusBadge').className = 'tag success';
      document.getElementById('liveStatusBadge').textContent = 'COMPLETED';
      document.getElementById('headerPulse').className = 'pulse-dot';
      document.getElementById('headerStatusText').textContent = 'Engine Ready';

      updateHUD('✨', 'Workflow Manager', 'done', `Workflow finished in ${ev.duration}s! Solution verified.`);
      addTimelineEvent('success', 'Workflow Complete', `Execution completed in ${ev.duration}s. All checks passed.`, '✨');
      showSummary(ev, 'success');

    } else if (status === 'rejected') {
      setPipelineNodeState('output', 'failed', 'Rejected ⚠️', null);

      document.getElementById('liveStatusBadge').className = 'tag hitl';
      document.getElementById('liveStatusBadge').textContent = 'REJECTED';
      document.getElementById('headerPulse').className = 'pulse-dot';
      document.getElementById('headerStatusText').textContent = 'Engine Ready';

      updateHUD('⚠️', 'Workflow Manager', 'approval', `Workflow stopped: Action rejected by user.`);
      addTimelineEvent('hitl', 'Action Rejected', `File modification was cancelled during Human-in-the-Loop review.`, '⚠️');
      showSummary(ev, 'rejected');

    } else {
      setPipelineNodeState('output', 'failed', 'Failed ✗', null);

      document.getElementById('liveStatusBadge').className = 'tag failed';
      document.getElementById('liveStatusBadge').textContent = 'FAILED';
      document.getElementById('headerPulse').className = 'pulse-dot';
      document.getElementById('headerStatusText').textContent = 'Engine Ready';

      updateHUD('❌', 'Workflow Manager', 'failed', `Workflow execution finished with errors.`);
      addTimelineEvent('hitl', 'Workflow Failed', `Execution encountered errors or could not apply changes.`, '❌');
      showSummary(ev, 'failed');
    }

  } else if (type === 'workflow_failed') {
    stopTimer();
    setPipelineNodeState('agent', 'failed', 'Error ✗', null);
    setPipelineNodeState('output', 'failed', 'Failed ✗', null);

    document.getElementById('liveStatusBadge').className = 'tag failed';
    document.getElementById('liveStatusBadge').textContent = 'FAILED';
    document.getElementById('headerPulse').className = 'pulse-dot';
    document.getElementById('headerStatusText').textContent = 'Engine Ready';

    updateHUD('❌', 'Error', 'failed', `Workflow failed: ${ev.error}`);
    addTimelineEvent('hitl', 'Workflow Failed', ev.error, '❌');
    showSummary({ trace_id: 'error', summary: `Workflow failed: ${ev.error}` }, 'failed');
  }

  // 2. Also stream to Terminal Console
  appendTerminalLog(ev, timeStr);
}

// Animated Action Timeline Feed Card
function addTimelineEvent(cardType, title, body, icon, isPre = false) {
  const container = document.getElementById('actionTimelineList');
  const card = document.createElement('div');
  card.className = `event-card ${cardType}`;

  const timeStr = new Date().toLocaleTimeString();
  card.innerHTML = `
    <div class="event-top">
      <span class="event-type-badge">${icon} ${escapeHtml(title)}</span>
      <span class="event-time">${timeStr}</span>
    </div>
    <div class="event-body">
      ${isPre ? `<pre class="event-pre">${escapeHtml(body)}</pre>` : escapeHtml(body)}
    </div>
  `;

  container.prepend(card);
}

// Terminal Console Streamer
function appendTerminalLog(ev, timeStr) {
  const term = document.getElementById('terminalOutput');
  const type = ev.type;
  let html = '';

  if (type === 'agent_start') {
    html = `<span class="log-time">${timeStr}</span><span class="log-content"><span class="log-agent">🤖 [${ev.agent}]</span> Started: ${escapeHtml(ev.task)}</span>`;
  } else if (type === 'thought') {
    html = `<span class="log-time">${timeStr}</span><span class="log-content log-thought">💭 ${escapeHtml(ev.thought)}</span>`;
  } else if (type === 'tool_call') {
    html = `<span class="log-time">${timeStr}</span><span class="log-content log-tool">• Executing tool: <b>${escapeHtml(ev.tool)}</b> ${ev.detail ? '(' + escapeHtml(ev.detail) + ')' : ''}</span>`;
  } else if (type === 'tool_error') {
    html = `<span class="log-time">${timeStr}</span><span class="log-content log-error">✗ Tool error (${escapeHtml(ev.tool)}): ${escapeHtml(ev.error)}</span>`;
  } else if (type === 'diff') {
    html = `<span class="log-time">${timeStr}</span><span class="log-content" style="color:#fde047;">📝 Patch for ${escapeHtml(ev.file_path)}:<br><pre style="color:#86efac; font-size:0.75rem;">${escapeHtml(ev.diff)}</pre></span>`;
  } else if (type === 'hitl_request') {
    html = `<span class="log-time">${timeStr}</span><span class="log-content log-gate">⚠️ Human Approval Required: ${escapeHtml(ev.action_name)}</span>`;
  } else if (type === 'hitl_resolved') {
    html = `<span class="log-time">${timeStr}</span><span class="log-content" style="color:#a7f3d0;">${ev.approved ? '✅ Action Approved' : '❌ Action Rejected'}</span>`;
  } else if (type === 'workflow_completed') {
    html = `<span class="log-time">${timeStr}</span><span class="log-content log-success">✨ Workflow finished in ${ev.duration}s</span>`;
  } else if (type === 'workflow_failed') {
    html = `<span class="log-time">${timeStr}</span><span class="log-content log-error">❌ Workflow failed: ${escapeHtml(ev.error)}</span>`;
  } else if (type === 'info' || type === 'success' || type === 'warning' || type === 'error') {
    html = `<span class="log-time">${timeStr}</span><span class="log-content log-${type}">${escapeHtml(ev.message)}</span>`;
  }

  if (html) {
    const line = document.createElement('div');
    line.className = 'log-line';
    line.innerHTML = html;
    term.appendChild(line);

    if (document.getElementById('autoScrollCheck').checked) {
      term.scrollTop = term.scrollHeight;
    }
  }
}

// Clear Terminal
function clearTerminal() {
  document.getElementById('terminalOutput').innerHTML = '';
}

// ==============================================================================
// 5. Human-in-the-Loop Web Modal
// ==============================================================================

function showHitlModal(ev) {
  activeHitlReqId = ev.req_id;
  const card = document.getElementById('hitlAlertCard');
  card.style.display = 'block';
  document.getElementById('hitlActionTitle').textContent = `Approval Required: ${ev.action_name}`;
  document.getElementById('hitlDetailsText').textContent = ev.details || '';

  const box = document.getElementById('hitlDiffBox');
  box.textContent = ev.diff || ev.command || '(No raw diff payload)';

  document.getElementById('headerPulse').className = 'pulse-dot hitl';
  document.getElementById('headerStatusText').textContent = 'Awaiting User Approval';
}

function hideHitlModal() {
  document.getElementById('hitlAlertCard').style.display = 'none';
  document.getElementById('hitlFeedbackInput').value = '';
  activeHitlReqId = null;

  document.getElementById('headerPulse').className = 'pulse-dot running';
  document.getElementById('headerStatusText').textContent = 'Engine Active';
}

async function resolveHitl(approved) {
  if (!activeHitlReqId) return;
  const feedback = document.getElementById('hitlFeedbackInput').value.trim();

  try {
    await fetch('/api/workflow/hitl/respond', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        req_id: activeHitlReqId,
        approved: approved,
        feedback: feedback,
      }),
    });
    hideHitlModal();
  } catch (err) {
    alert('Failed to respond to approval: ' + err.message);
  }
}

// Final Summary Outcome Card
function showSummary(ev, outcomeStatus = 'success') {
  const card = document.getElementById('summaryCard');
  card.style.display = 'block';

  const titleEl = document.getElementById('summaryCardTitle');
  const traceTag = document.getElementById('summaryTraceTag');

  traceTag.textContent = ev.trace_id || 'trace-done';

  if (outcomeStatus === 'rejected') {
    card.style.borderColor = 'rgba(245, 158, 11, 0.4)';
    card.style.background = 'linear-gradient(145deg, rgba(245, 158, 11, 0.1), rgba(244, 63, 94, 0.05))';
    if (titleEl) {
      titleEl.textContent = '⚠️ Workflow Stopped: Action Rejected by User';
      titleEl.style.color = '#f59e0b';
    }
    traceTag.className = 'tag hitl';
  } else if (outcomeStatus === 'failed') {
    card.style.borderColor = 'rgba(244, 63, 94, 0.4)';
    card.style.background = 'linear-gradient(145deg, rgba(244, 63, 94, 0.1), rgba(0, 0, 0, 0.3))';
    if (titleEl) {
      titleEl.textContent = '❌ Workflow Execution Failed with Errors';
      titleEl.style.color = '#fb7185';
    }
    traceTag.className = 'tag failed';
  } else {
    card.style.borderColor = 'rgba(16, 185, 129, 0.3)';
    card.style.background = 'linear-gradient(145deg, rgba(16, 185, 129, 0.1), rgba(6, 182, 212, 0.05))';
    if (titleEl) {
      titleEl.textContent = '✨ Workflow Execution Completed Successfully';
      titleEl.style.color = '#34d399';
    }
    traceTag.className = 'tag success';
  }

  document.getElementById('summaryMarkdown').textContent = ev.summary || 'Completed with no additional summary details.';
}

// Timer
let startTime = 0;
function startTimer() {
  startTime = Date.now();
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    const elapsed = (Date.now() - startTime) / 1000;
    const mins = Math.floor(elapsed / 60);
    const secs = (elapsed % 60).toFixed(1);
    const formatted = `${String(mins).padStart(2, '0')}:${String(secs).padStart(4, '0')}`;
    document.getElementById('liveTimer').textContent = formatted;
  }, 100);
}

function stopTimer() {
  if (timerInterval) clearInterval(timerInterval);
}

// ==============================================================================
// 6. Files & Tests Explorer
// ==============================================================================

async function refreshFileTree() {
  const targetDir = document.getElementById('targetDirInput').value.trim() || 'demo_target_project';
  try {
    const resp = await fetch(`/api/files/tree?target_dir=${encodeURIComponent(targetDir)}`);
    const data = await resp.json();
    document.getElementById('fileTreeRoot').textContent = data.root;
    const list = document.getElementById('fileTreeList');
    list.innerHTML = '';

    if (!data.files || data.files.length === 0) {
      list.innerHTML = '<li class="file-item">No files found</li>';
      return;
    }

    data.files.forEach((f) => {
      const li = document.createElement('li');
      li.className = 'file-item';
      li.innerHTML = `<span>📄</span> <span>${f.path}</span>`;
      li.onclick = () => loadFileContent(f.path, targetDir);
      list.appendChild(li);
    });

    if (data.files.length > 0) {
      loadFileContent(data.files[0].path, targetDir);
    }
  } catch (err) {
    console.error(err);
  }
}

async function loadFileContent(path, targetDir) {
  document.querySelectorAll('.file-item').forEach((i) => i.classList.remove('active'));
  const activeEl = Array.from(document.querySelectorAll('.file-item')).find((el) =>
    el.textContent.includes(path)
  );
  if (activeEl) activeEl.classList.add('active');

  document.getElementById('activeFilePath').textContent = path;
  document.getElementById('codeViewerBody').textContent = 'Loading...';

  try {
    const resp = await fetch(
      `/api/files/read?path=${encodeURIComponent(path)}&target_dir=${encodeURIComponent(targetDir)}`
    );
    const data = await resp.json();

    const lines = data.content.split('\n');
    const numbered = lines
      .map(
        (l, i) =>
          `<span style="color:#64748b; user-select:none; width:35px; display:inline-block;">${
            i + 1
          }</span> ${escapeHtml(l)}`
      )
      .join('\n');
    document.getElementById('codeViewerBody').innerHTML = numbered;
  } catch (err) {
    document.getElementById('codeViewerBody').textContent = 'Failed to load file content: ' + err.message;
  }
}

async function runPytestInBrowser() {
  const targetDir = document.getElementById('targetDirInput').value.trim() || 'demo_target_project';
  document.getElementById('codeViewerBody').textContent = 'Running pytest test suite on ' + targetDir + '...';
  try {
    const resp = await fetch(`/api/tests/run?target_dir=${encodeURIComponent(targetDir)}`, {
      method: 'POST',
    });
    const data = await resp.json();
    document.getElementById('codeViewerBody').textContent = data.result;
  } catch (err) {
    document.getElementById('codeViewerBody').textContent = 'Test run failed: ' + err.message;
  }
}

// ==============================================================================
// 7. Telemetry & Observability
// ==============================================================================

async function loadTelemetry() {
  try {
    const resp = await fetch('/api/traces');
    const traces = await resp.json();

    document.getElementById('metricTraces').textContent = traces.length;

    let totalSpans = 0;
    let totalTokens = 0;
    traces.forEach((t) => {
      totalSpans += (t.spans || []).length;
      totalTokens += t.total_tokens || 0;
    });

    document.getElementById('metricSpans').textContent = totalSpans;
    document.getElementById('metricTokens').textContent = totalTokens.toLocaleString();

    const tbody = document.getElementById('tracesTableBody');
    tbody.innerHTML = '';

    if (!traces || traces.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No recorded traces yet.</td></tr>';
      return;
    }

    traces.forEach((t) => {
      const tr = document.createElement('tr');
      const time = new Date(t.start_time * 1000).toLocaleTimeString();
      const tagClass =
        t.status === 'success' || t.status === 'completed'
          ? 'success'
          : t.status === 'in_progress'
          ? 'running'
          : 'failed';
      tr.innerHTML = `
        <td><code>${t.trace_id}</code></td>
        <td><b>${escapeHtml(t.task_description.slice(0, 50))}${t.task_description.length > 50 ? '...' : ''}</b></td>
        <td><code>${escapeHtml(t.target_project.split(/[\\/]/).pop())}</code></td>
        <td>${(t.spans || []).length}</td>
        <td><span class="tag ${tagClass}">${t.status.toUpperCase()}</span></td>
        <td>${time}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error(err);
  }
}

function escapeHtml(str) {
  if (typeof str !== 'string') return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ==============================================================================
// 8. Auto-Initialization
// ==============================================================================

window.addEventListener('DOMContentLoaded', () => {
  connectSSE();

  // Load config defaults
  fetch('/api/config')
    .then((r) => r.json())
    .then((c) => {
      if (c.target_project_path) {
        document.getElementById('targetDirInput').value = c.target_project_path;
      }
      if (c.model_name) {
        document.getElementById('modelInput').value = c.model_name;
      }
      if (c.llm_provider) {
        document.getElementById('providerSelect').value = c.llm_provider;
      }
      if (c.hitl_enabled) {
        document.getElementById('hitlToggle').checked = c.hitl_enabled;
      }
    })
    .catch(() => {});
});
