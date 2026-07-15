// upload.js — 文件上传与拖拽逻辑
const Upload = (() => {
  let videoFile = null;
  let subFile = null;

  const fmtSize = (b) => {
    if (!b) return '-';
    const u = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
    return b.toFixed(1) + ' ' + u[i];
  };

  const setupDrop = (dropEl, onFile) => {
    const input = dropEl.querySelector('input');
    dropEl.addEventListener('dragover', e => {
      e.preventDefault();
      dropEl.classList.add('dragover');
    });
    dropEl.addEventListener('dragleave', () => {
      dropEl.classList.remove('dragover');
    });
    dropEl.addEventListener('drop', e => {
      e.preventDefault();
      dropEl.classList.remove('dragover');
      const f = e.dataTransfer.files[0];
      if (f) onFile(f);
    });
    dropEl.addEventListener('click', () => input.click());
    input.addEventListener('change', () => {
      const f = input.files[0];
      if (f) onFile(f);
    });
  };

  const setVideoFile = (f) => {
    videoFile = f;
    const drop = $('#videoDrop');
    drop.classList.add('has-file');
    $('#videoInfo').style.display = 'block';
    $('#videoInfo').textContent = f.name + ' (' + fmtSize(f.size) + ')';
    checkReady();
  };

  const setSubFile = (f) => {
    subFile = f;
    const drop = $('#subDrop');
    drop.classList.add('has-file');
    $('#subInfo').style.display = 'block';
    $('#subInfo').textContent = f.name + ' (' + fmtSize(f.size) + ')';
    checkReady();
  };

  const isReady = () => videoFile && subFile;

  const reset = () => {
    videoFile = null;
    subFile = null;
    $('#videoDrop').classList.remove('has-file');
    $('#subDrop').classList.remove('has-file');
    $('#videoInfo').style.display = 'none';
    $('#subInfo').style.display = 'none';
    checkReady();
  };

  const getVideoFile = () => videoFile;
  const getSubFile = () => subFile;

  return { setupDrop, setVideoFile, setSubFile, isReady, reset, getVideoFile, getSubFile };
})();
