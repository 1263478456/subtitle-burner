// utils.js — 通用工具函数
const Utils = (() => {
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

  const toast = (msg, kind) => {
    const t = $('#toast');
    if (!t) return;
    t.textContent = msg;
    t.className = 'toast show ' + (kind || 'success');
    setTimeout(() => t.classList.remove('show'), 3000);
  };

  return { $, $$, toast };
})();
