// queue.js — 任务轮询、进度更新与批量烧录（惰性依赖 Utils，避免加载顺序问题）
const Queue = (() => {
  const $ = (s) => document.querySelector(s);
  const toast = (msg, kind) => {
    const t = document.querySelector('#toast');
    if (!t) return;
    t.textContent = msg;
    t.className = 'toast show ' + (kind || 'success');
    setTimeout(() => t.classList.remove('show'), 3000);
  };
  let pollTimer = null;
  let batchTotal = 0;
  let batchCompleted = 0;

  const addLocalTask = (taskId, name) => {
    const list = $('#taskList');
    if (list.querySelector('.empty')) list.innerHTML = '';
    const div = document.createElement('div');
    div.className = 'task-item';
    div.id = 'task-' + taskId;
    div.innerHTML = '<div class="task-head"><span class="task-name">' + name + '</span><span class="task-id">' + taskId + '</span></div><div class="status queued">queued</div><div class="progress-wrap"><div class="progress-bar" id="pb-' + taskId + '"></div></div>';
    list.prepend(div);
  };

  const updateTaskUI = (t) => {
    const el = document.getElementById('task-' + t.task_id);
    if (!el) return;
    const statusEl = el.querySelector('.status');
    statusEl.className = 'status ' + t.status;
    statusEl.textContent = t.status === 'processing' ? 'processing ' + (t.progress || 0) + '%' : t.status;
    const pb = document.getElementById('pb-' + t.task_id);
    if (pb) pb.style.width = (t.progress || 0) + '%';
    if (t.status === 'completed' || t.status === 'failed') {
      if (!el.querySelector('.task-actions')) {
        const div = document.createElement('div');
        div.className = 'task-actions';
        if (t.status === 'completed') div.innerHTML = '<button onclick="Queue.downloadTask(\'' + t.task_id + '\')">download</button>';
        if (t.status === 'failed') div.innerHTML += '<button class="retry" onclick="Queue.retryTask(\'' + t.task_id + '\')">retry</button>';
        div.innerHTML += '<button class="delete" onclick="Queue.removeTask(\'' + t.task_id + '\')">delete</button>';
        el.appendChild(div);
      }
    }
  };

  const updateBatchProgress = () => {
    if (batchTotal === 0) return;
    const pct = Math.round((batchCompleted / batchTotal) * 100);
    const fill = $('#batchProgressFill');
    const label = $('#batchProgressLabel');
    if (fill) fill.style.width = pct + '%';
    if (label) label.textContent = `Batch progress: ${batchCompleted}/${batchTotal} (${pct}%)`;
  };

  const pollTasks = () => {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      try {
        const r = await fetch('/api/queue');
        if (!r.ok) return;
        const data = await r.json();
        const items = Array.isArray(data) ? data : (data.tasks || []);
        items.forEach(t => updateTaskUI(t));
        if (items.length && items.every(t => t.status === 'completed' || t.status === 'failed')) {
          clearInterval(pollTimer);
          pollTimer = null;
          // 批量完成，隐藏批量进度条
          const bp = $('#batchProgress');
          if (bp) bp.style.display = 'none';
        }
      } catch (e) { /* ignore poll errors */ }
    }, 2000);
  };

  const downloadTask = (id) => { window.location.href = '/api/download/' + id; };
  const removeTask = (id) => { const el = document.getElementById('task-' + id); if (el) el.remove(); };

  const startBurn = async () => {
    const btn = $('#burnBtn');
    btn.disabled = true;
    try {
      if (mode === 'upload') {
        const fd = new FormData();
        fd.append('video', Upload.getVideoFile());
        fd.append('subtitle', Upload.getSubFile());
        const upRes = await fetch('/api/upload', { method: 'POST', body: fd });
        if (!upRes.ok) throw new Error((await upRes.json()).detail || 'Upload failed');
        const upData = await upRes.json();
        await burnTask(upData.task_id, Upload.getVideoFile().name, Upload.getSubFile().name);
      } else {
        await batchBurn();
        return;
      }
    } catch (e) {
      toast(e.message, 'error');
      btn.disabled = false;
    }
  };

  const burnTask = async (taskId, vName, sName) => {
    const fd = new FormData();
    fd.append('task_id', taskId);
    fd.append('video_name', vName);
    fd.append('subtitle_name', sName);
    fd.append('crf', $('#crf').value);
    fd.append('preset', $('#preset').value);
    fd.append('codec', $('#codec').value);
    fd.append('style', $('#style').value);
    const r = await fetch('/api/burn', { method: 'POST', body: fd });
    if (!r.ok) throw new Error((await r.json()).detail || 'Submit failed');
    toast('Task queued');
    addLocalTask(taskId, vName);
    pollTasks();
  };

  const batchBurn = async () => {
    const pairs = Media.getPairs();
    if (pairs.length === 0) return;
    const btn = $('#burnBtn');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Submitting...';
    batchTotal = pairs.length;
    batchCompleted = 0;

    // 显示批量进度条
    let bp = $('#batchProgress');
    if (!bp) {
      bp = document.createElement('div');
      bp.id = 'batchProgress';
      bp.className = 'batch-progress';
      bp.innerHTML = '<div class="batch-progress-label" id="batchProgressLabel">Batch progress: 0/' + batchTotal + ' (0%)</div><div class="batch-progress-bar"><div class="batch-progress-fill" id="batchProgressFill"></div></div>';
      $('#burnPanel').appendChild(bp);
    } else {
      bp.style.display = 'block';
    }
    updateBatchProgress();

    let ok = 0, fail = 0;
    for (const p of pairs) {
      try {
        const fd = new FormData();
        fd.append('video_path', p.videoPath);
        fd.append('subtitle_path', p.subPath);
        fd.append('crf', p.crf);
        fd.append('preset', p.preset);
        fd.append('codec', p.codec);
        fd.append('style', p.style);
        const r = await fetch('/api/media/burn', { method: 'POST', body: fd });
        if (!r.ok) throw new Error((await r.json()).detail || 'Submit failed');
        const data = await r.json();
        addLocalTask(data.task_id, data.video_name);
        ok++;
      } catch (e) { fail++; }
      batchCompleted++;
      updateBatchProgress();
    }
    btn.textContent = originalText || 'Batch burn all pairs';
    btn.disabled = false;
    toast('Done: ' + ok + ' success, ' + fail + ' failed');
    if (ok > 0) pollTasks();
  };

  const clearCompleted = () => {
    document.querySelectorAll('.task-item').forEach(el => {
      const statusEl = el.querySelector('.status');
      if (statusEl && (statusEl.classList.contains('completed') || statusEl.classList.contains('failed'))) {
        el.remove();
      }
    });
    const list = $('#taskList');
    if (!list.querySelector('.task-item')) {
      list.innerHTML = '<div class="empty">暂无任务</div>';
    }
  };

  const retryTask = async (taskId) => {
    try {
      const r = await fetch('/api/retry/' + taskId, { method: 'POST' });
      if (!r.ok) throw new Error((await r.json()).detail || 'Retry failed');
      toast('Task ' + taskId + ' requeued');
      // 更新本地 UI
      const el = document.getElementById('task-' + taskId);
      if (el) {
        const statusEl = el.querySelector('.status');
        statusEl.className = 'status queued';
        statusEl.textContent = 'queued';
        const pb = document.getElementById('pb-' + taskId);
        if (pb) pb.style.width = '0%';
        // 移除操作按钮（如果有）
        const actions = el.querySelector('.task-actions');
        if (actions) actions.remove();
      }
    } catch (e) {
      toast(e.message, 'error');
    }
  };

  return {
    addLocalTask, updateTaskUI, pollTasks,
    downloadTask, removeTask, startBurn, burnTask, batchBurn, clearCompleted, retryTask
  };
})();
