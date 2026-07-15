// media.js — 媒体库浏览与配对逻辑
const Media = (() => {
  const { $, $$, toast } = Utils;
  let mediaPath = '';
  let selectedVideoMedia = null;
  let selectedSubMedia = null;
  let mediaPairs = [];

  const fmtSize = (b) => {
    if (!b) return '-';
    const u = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
    return b.toFixed(1) + ' ' + u[i];
  };

  const updatePairUI = () => {
    const sec = $('#pairSection');
    if (!sec) return;
    const cnt = $('#pairCount');
    const list = $('#pairList');
    sec.style.display = (mediaPairs.length > 0) ? 'block' : 'none';
    cnt.textContent = mediaPairs.length;
    list.innerHTML = mediaPairs.map((p, i) =>
      '<div class="pair-row">' +
      '<span class="vid" title="' + p.videoPath + '">V ' + p.videoName + '</span>' +
      '<span class="sep">+</span>' +
      '<span class="sub" title="' + p.subPath + '"> S ' + p.subName + '</span>' +
      '<button class="del-pair" onclick="Media.removePair(' + i + ')">x</button>' +
      '</div>'
    ).join('');
    if (typeof checkReady === 'function') checkReady();
  };

  const addPair = (videoPath, videoName, subPath, subName) => {
    const dup = mediaPairs.find(p => p.videoPath === videoPath && p.subPath === subPath);
    if (dup) return;
    mediaPairs.push({
      videoPath, videoName, subPath, subName,
      crf: $('#crf').value, preset: $('#preset').value,
      codec: $('#codec').value, style: $('#style').value
    });
    updatePairUI();
    toast('Paired: ' + videoName + ' + ' + subName);
  };

  const removePair = (i) => {
    mediaPairs.splice(i, 1);
    updatePairUI();
  };

  const clearPairs = () => {
    mediaPairs = [];
    selectedVideoMedia = null;
    selectedSubMedia = null;
    updatePairUI();
  };

  const smartPair = () => {
    const items = Array.from($$('.media-item[data-type]'));
    const videos = items.filter(el => el.dataset.type === 'video');
    const subs = items.filter(el => el.dataset.type === 'sub');
    let added = 0;
    videos.forEach(vEl => {
      const vPath = vEl.dataset.path;
      const vName = vPath.split('/').pop();
      const vBase = vName.replace(/\.[^.]+$/, '');
      subs.forEach(sEl => {
        const sPath = sEl.dataset.path;
        const sName = sPath.split('/').pop();
        const sBase = sName.replace(/\.[^.]+$/, '');
        if (vBase === sBase && !mediaPairs.find(p => p.videoPath === vPath && p.subPath === sPath)) {
          mediaPairs.push({
            videoPath: vPath, videoName: vName, subPath: sPath, subName: sName,
            crf: $('#crf').value, preset: $('#preset').value,
            codec: $('#codec').value, style: $('#style').value
          });
          added++;
        }
      });
    });
    updatePairUI();
    if (added > 0) toast('Smart paired: ' + added + ' pairs');
    else toast('No matching pairs found', 'error');
  };

  const loadMedia = async (path) => {
    path = path || '';
    mediaPath = path;
    const r = await fetch('/api/media/list?path=' + encodeURIComponent(path));
    if (!r.ok) { toast((await r.json()).detail, 'error'); return; }
    const data = await r.json();
    $('#mediaBreadcrumb').textContent = ' /' + (data.current_path || '');
    const list = $('#mediaList');
    list.innerHTML = '';
    if (!data.items.length) { list.innerHTML = '<div class="empty">empty</div>'; return; }

    const mediaArea = $('#tab-media-area');
    const oldInd = mediaArea.querySelector('.selection-indicator');
    if (oldInd) oldInd.remove();

    let indHtml = '';
    if (selectedVideoMedia) indHtml += '<span class="tag vid">V: ' + selectedVideoMedia.split('/').pop() + '</span>';
    if (selectedSubMedia) indHtml += '<span class="tag sub"> S: ' + selectedSubMedia.split('/').pop() + '</span>';
    if (!selectedVideoMedia && !selectedSubMedia) indHtml = '<span class="tag none">Click video then subtitle to pair</span>';

    const indDiv = document.createElement('div');
    indDiv.className = 'selection-indicator';
    indDiv.innerHTML = indHtml;
    mediaArea.insertBefore(indDiv, mediaArea.firstChild);

    data.items.forEach(it => {
      const div = document.createElement('div');
      div.className = 'media-item';
      if (it.is_dir) {
        div.innerHTML = '<span class="ic">DIR</span><div class="nm">' + it.name + '</div>';
        div.onclick = () => loadMedia(it.path);
      } else {
        const ext = it.ext;
        const isVid = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts', '.m4v', '.mpg', '.mpeg'].includes(ext);
        const isSub = ['.srt', '.vtt', '.ass', '.ssa', '.sub'].includes(ext);
        div.dataset.path = it.path;
        div.dataset.type = isVid ? 'video' : isSub ? 'sub' : 'other';
        div.innerHTML = '<span class="ic">' + (isVid ? 'V' : isSub ? 'S' : 'F') + '</span><div class="nm">' + it.name + '</div><div class="sz">' + fmtSize(it.size) + '</div>';
        if (isVid && it.path === selectedVideoMedia) div.style.borderColor = '#3b82f6';
        if (isSub && it.path === selectedSubMedia) div.style.borderColor = '#8b5cf6';
        if (isVid || isSub) {
          div.onclick = () => {
            if (isVid) selectedVideoMedia = (selectedVideoMedia === it.path) ? null : it.path;
            else selectedSubMedia = (selectedSubMedia === it.path) ? null : it.path;
            if (selectedVideoMedia && selectedSubMedia) {
              const vName = selectedVideoMedia.split('/').pop();
              const sName = selectedSubMedia.split('/').pop();
              addPair(selectedVideoMedia, vName, selectedSubMedia, sName);
              selectedVideoMedia = null;
              selectedSubMedia = null;
            }
            loadMedia(path);
          };
        }
      }
      list.appendChild(div);
    });
    updatePairUI();
  };

  const getPairs = () => mediaPairs;
  const clearAllPairs = clearPairs;

  const setTab = (tab) => {
    const uploadBtn = $('#tab-upload');
    const mediaBtn = $('#tab-media');
    const uploadArea = $('#tab-upload-area');
    const mediaArea = $('#tab-media-area');

    if (!uploadBtn || !mediaBtn || !uploadArea || !mediaArea) return;

    if (tab === 'upload') {
      uploadBtn.classList.add('active');
      mediaBtn.classList.remove('active');
      uploadArea.style.display = 'block';
      mediaArea.style.display = 'none';
      if (typeof mode !== 'undefined') mode = 'upload';
      if (typeof checkReady === 'function') checkReady();
    } else if (tab === 'media') {
      uploadBtn.classList.remove('active');
      mediaBtn.classList.add('active');
      uploadArea.style.display = 'none';
      mediaArea.style.display = 'block';
      if (typeof mode !== 'undefined') mode = 'media';
      // 如果媒体列表还没加载实际内容，自动加载根目录
      const list = $('#mediaList');
      if (list && !list.querySelector('.media-item')) {
        loadMedia('');
      }
      // 确保配对区域可见，并刷新按钮状态
      const sec = $('#pairSection');
      if (sec) sec.style.display = 'block';
      if (typeof checkReady === 'function') checkReady();
    }
  };

  return {
    loadMedia, addPair, removePair, clearPairs, smartPair,
    getPairs, clearAllPairs, updatePairUI, setTab
  };
})();

// 挂载到全局作用域，因为 HTML onclick 直接调用 setTab
window.setTab = Media.setTab;
