/* Deck detail actions; content is server-rendered and stays readable without this script. */
(function () {
  'use strict';
  const D = window.JccOrangeDeck;
  const deck = JSON.parse(document.getElementById('deckData').textContent);
  const actions = document.getElementById('deckActions');
  const status = document.getElementById('deckActionStatus');
  let session = { user: null, csrf: '' };
  D.bindTheme();
  const say = (text, error = false) => { status.textContent = text; status.classList.toggle('deck-error', error); };

  async function favorite(control) {
    if (!session.user) { say('登录后可以收藏卡组。'); return; }
    const data = await D.api(`/api/orange-decks/${deck.id}/favorite`, { method: deck.is_favorited ? 'DELETE' : 'POST', csrf: session.csrf });
    deck.is_favorited = data.favorited;
    control.setAttribute('aria-pressed', String(data.favorited));
    control.textContent = data.favorited ? '已收藏' : '收藏';
    document.getElementById('deckFavoriteCount').textContent = data.favorite_count;
    say(data.favorited ? '已收藏，可在卡组库的“我的收藏”找回。' : '已取消收藏。');
  }

  async function fork() {
    if (!session.user) { say('登录后可以以此为基础创建自己的卡组。'); return; }
    const data = await D.api(`/api/orange-decks/${deck.id}/fork`, { method: 'POST', csrf: session.csrf });
    // The new draft is always a separate deck; the author's deck and earlier drafts are untouched.
    try { sessionStorage.setItem('jcc-orange-deck-notice', JSON.stringify(['已创建新的草稿，原卡组不受影响。', ...data.notes])); } catch { /* Notice is optional. */ }
    location.href = data.edit_url;
  }

  async function remove() {
    if (!confirm(`确定删除“${deck.name}”吗？删除后详情、搜索和分享链接都将失效。`)) return;
    await D.api(`/api/orange-decks/${deck.id}`, { method: 'DELETE', csrf: session.csrf });
    location.href = '/?library=decks&tab=mine';
  }

  actions.addEventListener('click', async (event) => {
    const control = event.target.closest('[data-action]');
    if (!control || control.disabled) return;
    control.disabled = true;
    try {
      const action = control.dataset.action;
      if (action === 'favorite') await favorite(control);
      else if (action === 'copy-text') say(await D.copy(deck.share_text) ? '已复制卡组文本（含详情链接）。' : '复制失败，请手动选择页面内容。', false);
      else if (action === 'copy-link') say(await D.copy(deck.share_url) ? '已复制详情链接。' : '复制失败，请从地址栏复制。', false);
      else if (action === 'fork') await fork();
      else if (action === 'delete') await remove();
    } catch (error) {
      say(error.message, true);
    } finally {
      control.disabled = false;
    }
  });

  try {
    const queued = JSON.parse(sessionStorage.getItem('jcc-orange-deck-notice') || '[]');
    sessionStorage.removeItem('jcc-orange-deck-notice');
    if (queued.length) say(queued.join(' '));
  } catch { /* Notice is optional. */ }
  D.api('/api/me').then((data) => { session = { user: data.user, csrf: data.csrf_token }; })
    .catch(() => say('登录状态暂时无法确认，收藏和创建可能不可用。', true))
    .finally(() => actions.querySelectorAll('button[disabled]').forEach((button) => { button.disabled = false; }));
})();
