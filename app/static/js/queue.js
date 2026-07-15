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

  const fmtETA = (seconds) => {
    if (!seconds || seconds < 0) return '';
    if (seconds < 60) return Math.ceil(seconds) + '秒';
    if (seconds < 3600) return Math.floor(seconds / 60) + '分' + Math.ceil(seconds % 60) + '秒';
    return Math.floor(seconds / 3600) + '时' + Math.floor((seconds % 3600) / 60) + '分';
  };

  const updateTaskUI = (t) => {
    const el = document.getElementById('task-' + t.task_id);
    if (!el) return;
    const statusEl = el.querySelector('.status');
    statusEl.className = 'status ' + t.status;
    const progressVal = parseFloat(t.progress) || 0;
    
    // 计算 ETA
    let etaText = '';
    if (t.status === 'processing' && progressVal > 0 && t.started_at) {
      const startTime = new Date(t.started_at).getTime();
      const now = Date.now();
      const elapsed = (now - startTime) / 1000; // 秒
      const remaining = elapsed * (100 - progressVal) / progressVal;
      etaText = ' · 剩余 ' + fmtETA(remaining);
    }
    
    statusEl.textContent = t.status === 'processing' ? '处理中 ' + progressVal.toFixed(2) + '%' + etaText : 
                           t.status === 'queued' ? '排队中' :
                           t.status === 'completed' ? '已完成' :
                           t.status === 'failed' ? '失败' : t.status;
    const pb = document.getElementById('pb-' + t.task_id);
    if (pb) pb.style.width = progressVal + '%';
    
    // 移除旧的操作按钮（状态变化时需要更新）
    const oldActions = el.querySelector('.task-actions');
    if (oldActions) oldActions.remove();
    
    // 根据状态添加操作按钮
    const div = document.createElement('div');
    div.className = 'task-actions';
    if (t.status === 'queued' || t.status === 'processing') {
      div.innerHTML = '<button class="stop" onclick="Queue.stopTask(\'' + t.task_id + '\')">⏹ 停止</button>';
    } else if (t.status === 'completed') {
      div.innerHTML = '<button onclick="Queue.downloadTask(\'' + t.task_id + '\')">下载</button>' +
                      '<button class="delete" onclick="Queue.removeTask(\'' + t.task_id + '\')">删除</button>';
    } else if (t.status === 'failed') {
      div.innerHTML = '<button class="retry" onclick="Queue.retryTask(\'' + t.task_id + '\')">重试</button>' +
                      '<button class="delete" onclick="Queue.removeTask(\'' + t.task_id + '\')">删除</button>';
    }
    if (div.innerHTML) el.appendChild(div);
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
    console.log('[startBurn] mode=' + window.mode);
    const btn = $('#burnBtn');
    if (btn) btn.disabled = true;
    try {
      if (window.mode === 'upload') {
        // 上传模式
        if (!Upload.getVideoFile() || !Upload.getSubFile()) {
          throw new Error('请先选择视频和字幕文件');
        }
        const fd = new FormData();
        fd.append('video', Upload.getVideoFile());
        fd.append('subtitle', Upload.getSubFile());
        const upRes = await fetch('/api/upload', { method: 'POST', body: fd });
        if (!upRes.ok) throw new Error((await upRes.json()).detail || 'Upload failed');
        const upData = await upRes.json();
        await burnTask(upData.task_id, Upload.getVideoFile().name, Upload.getSubFile().name);
      } else {
        // 媒体库批量模式
        await batchBurn();
        return;
      }
    } catch (e) {
      console.error('[startBurn] error:', e);
      toast(e.message, 'error');
      if (btn) btn.disabled = false;
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
    fd.append('sub_mode', $('#subMode').value);
    fd.append('keep_original_sub', $('#keepOriginalSub').value === 'true');
    
    // 添加预览参数
    const previewParams = localStorage.getItem('subtitlePreviewParams');
    if (previewParams) {
      fd.append('preview_params', previewParams);
    }
    
    const r = await fetch('/api/burn', { method: 'POST', body: fd });
    if (!r.ok) throw new Error((await r.json()).detail || 'Submit failed');
    toast('任务已排队');
    addLocalTask(taskId, vName);
    pollTasks();
  };

  const batchBurn = async () => {
    const pairs = Media.getPairs();
    console.log('[batchBurn] pairs=' + pairs.length);
    if (pairs.length === 0) {
      toast('请先配对视频和字幕文件', 'error');
      const btn = $('#burnBtn');
      if (btn) btn.disabled = false;
      return;
    }
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
        fd.append('crf', $('#crf').value);
        fd.append('preset', $('#preset').value);
        fd.append('codec', $('#codec').value);
        fd.append('style', $('#style').value);
        fd.append('sub_mode', $('#subMode').value);
        fd.append('keep_original_sub', $('#keepOriginalSub').value === 'true');
        
        // 添加预览参数
        const previewParams = localStorage.getItem('subtitlePreviewParams');
        if (previewParams) {
          fd.append('preview_params', previewParams);
        }
        
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
      toast('任务已重新排队');
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

  const stopTask = async (taskId) => {
    if (!confirm('确定要停止这个任务吗？')) return;
    try {
      const r = await fetch('/api/stop/' + taskId, { method: 'POST' });
      if (!r.ok) throw new Error((await r.json()).detail || 'Stop failed');
      toast('任务已停止');
      // 更新本地 UI
      const el = document.getElementById('task-' + taskId);
      if (el) {
        const statusEl = el.querySelector('.status');
        statusEl.className = 'status failed';
        statusEl.textContent = 'stopped';
        const pb = document.getElementById('pb-' + taskId);
        if (pb) pb.style.width = '0%';
        // 移除操作按钮并重新渲染
        const actions = el.querySelector('.task-actions');
        if (actions) actions.remove();
        // 添加重试和删除按钮
        const div = document.createElement('div');
        div.className = 'task-actions';
        div.innerHTML = '<button class="retry" onclick="Queue.retryTask(\'' + taskId + '\')">重试</button><button class="delete" onclick="Queue.removeTask(\'' + taskId + '\')">删除</button>';
        el.appendChild(div);
      }
    } catch (e) {
      toast(e.message, 'error');
    }
  };

  return {
    addLocalTask, updateTaskUI, pollTasks,
    downloadTask, removeTask, startBurn, burnTask, batchBurn, clearCompleted, retryTask, stopTask
  };
})();

window.Queue = Queue;
