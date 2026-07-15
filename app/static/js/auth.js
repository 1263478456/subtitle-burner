// auth.js — 认证与会话管理（惰性依赖 Utils，避免加载顺序问题）
const Auth = (() => {
  const $ = (s) => document.querySelector(s);
  const toast = (msg, kind) => {
    const t = document.querySelector('#toast');
    if (!t) return;
    t.textContent = msg;
    t.className = 'toast show ' + (kind || 'success');
    setTimeout(() => t.classList.remove('show'), 3000);
  };
  let currentUser = null;

  const getCurrentUser = () => currentUser;

  const checkAuth = async () => {
    try {
      const r = await fetch('/api/me');
      if (!r.ok) {
        location.href = '/login';
        return null;
      }
      currentUser = await r.json();
      return currentUser;
    } catch {
      location.href = '/login';
      return null;
    }
  };

  const logout = async () => {
    await fetch('/api/logout', { method: 'POST' });
    location.href = '/login';
  };

  const init = async () => {
    const user = await checkAuth();
    if (user) {
      const nameEl = $('userName');
      if (nameEl) nameEl.textContent = ' user ' + user.user;
    }
  };

  return { getCurrentUser, checkAuth, logout, init };
})();
