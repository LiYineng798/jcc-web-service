/* Deck detail actions; content is server-rendered and stays readable without this script. */
(function () {
  'use strict';
  const D = window.JccOrangeDeck;
  const deck = JSON.parse(document.getElementById('deckData').textContent);
  const actions = document.getElementById('deckActions');
  const status = document.getElementById('deckActionStatus');
  let session = { user: null, csrf: '' };
  D.bindTheme();
  for (const [type, label, buttonId, statusId] of [
    ['plan', '方案码', 'copyDeckPlan', 'deckCopyStatus'],
    ['lineup', '阵容码', 'copyDeckLineup', 'deckLineupCopyStatus'],
  ]) document.getElementById(buttonId)?.addEventListener('click', async (event) => {
    const control = event.currentTarget;
    control.disabled = true;
    try {
      const ok = await D.copy(deck[type + '_code']);
      document.getElementById(statusId).textContent = ok ? `${label}已复制` : `复制失败，请选择上方${label}手动复制`;
      if (ok && deck.status === 'published') {
        try { deck.copy_count = (await D.recordCopy(deck.id, session.csrf, type, 'detail')).copy_count; }
        catch { document.getElementById(statusId).textContent = `${label}已复制，但次数未同步，请稍后刷新`; }
      }
    } catch { document.getElementById(statusId).textContent = `复制失败，请选择上方${label}手动复制`; }
    finally { control.disabled = false; }
  });
  const say = (text, error = false) => { if (!status) return; status.textContent = text; status.classList.toggle('deck-error', error); };

  // The author avatar reacts to likes and favorites exactly as on lineup pages.
  const fallback = document.getElementById('deckAuthorAvatar');
  const avatar = D.avatar(deck.author, 30, `deck-detail-${deck.id}`);
  if (avatar && fallback) fallback.replaceWith(avatar);
  const feedback = (kind) => { try { if (avatar) window.jccAvatar?.feedback?.(avatar, kind); } catch { /* Decorative only. */ } };

  function label(control, text) { control.querySelector('span').textContent = text; }

  async function like(control) {
    if (!session.user) { say('登录后可以点赞卡组。'); return; }
    if (deck.is_liked_today) { say('今天已经点赞过这套卡组。'); return; }
    const data = await D.api(`/api/orange-decks/${deck.id}/like`, { method: 'POST', csrf: session.csrf });
    deck.is_liked_today = true;
    control.setAttribute('aria-pressed', 'true');
    label(control, '今日已赞');
    document.getElementById('deckLikeCount').textContent = data.like_count;
    feedback('like');
    say('');
  }

  async function favorite(control) {
    if (!session.user) { say('登录后可以收藏卡组。'); return; }
    const data = await D.api(`/api/orange-decks/${deck.id}/favorite`, { method: deck.is_favorited ? 'DELETE' : 'POST', csrf: session.csrf });
    deck.is_favorited = data.favorited;
    control.setAttribute('aria-pressed', String(data.favorited));
    label(control, data.favorited ? '已收藏' : '收藏');
    document.getElementById('deckFavoriteCount').textContent = data.favorite_count;
    if (data.favorited) feedback('favorite');
    say('');
  }

  async function remove() {
    if (!confirm(`确定删除“${deck.name}”吗？删除后详情、搜索和分享链接都将失效。`)) return;
    await D.api(`/api/orange-decks/${deck.id}`, { method: 'DELETE', csrf: session.csrf });
    location.href = '/?library=decks&tab=mine';
  }

  actions?.addEventListener('click', async (event) => {
    const control = event.target.closest('button[data-action]');
    if (!control || control.disabled) return;
    control.disabled = true;
    try {
      const action = control.dataset.action;
      if (action === 'like') await like(control);
      else if (action === 'favorite') await favorite(control);
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
    .catch(() => say('登录状态暂时无法确认，点赞和收藏可能不可用。', true))
    .finally(() => actions?.querySelectorAll('button[disabled]').forEach((button) => { button.disabled = false; }));
})();
