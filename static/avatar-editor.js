(() => {
  function mount(user, csrfToken) {
    const section = document.createElement('section');
    section.className = 'avatar-account panel';
    section.id = 'avatar';
    section.innerHTML = `<div class="avatar-account-identity"><div id="savedAvatar"></div><div><p class="section-kicker">我的形象</p><h2 id="avatarNickname"></h2><p class="avatar-caption">一枚属于你的色彩签名</p></div></div><button type="button" class="small-button" id="editAvatar">调整头像</button>`;
    section.querySelector('#avatarNickname').textContent = user.nickname || user.username;
    const savedImage = window.jccAvatar.image(user.avatar_color, 80, '我的头像');
    section.querySelector('#savedAvatar').append(savedImage);
    document.querySelector('.account-page-shell > .panel').before(section);

    const dialog = document.createElement('dialog');
    dialog.className = 'avatar-dialog';
    dialog.setAttribute('aria-labelledby', 'avatarEditorTitle');
    dialog.innerHTML = `<form class="avatar-editor">
      <header class="avatar-editor-head"><div><p class="section-kicker">个人形象</p><h2 id="avatarEditorTitle">让色彩代表你</h2></div><button type="button" class="avatar-close" aria-label="关闭头像编辑">×</button></header>
      <div class="avatar-editor-body"><div class="avatar-preview-stage"><div id="avatarLargePreview"></div><p>条纹球体</p><span>固定形态 · 自由配色</span><div class="avatar-size-preview" aria-label="小尺寸头像预览"></div></div>
      <div class="avatar-controls"><h3>推荐配色</h3><p class="avatar-caption">选择一种色调，或调出自己的颜色。</p><div class="avatar-swatches" role="group" aria-label="推荐配色"></div>
      <label class="avatar-color-label" for="avatarHex">自定义颜色</label><div class="avatar-color-inputs"><input id="avatarColor" type="color" aria-label="选择头像颜色"><input id="avatarHex" type="text" maxlength="7" pattern="#[0-9a-fA-F]{6}" required spellcheck="false" aria-describedby="avatarFeedback"></div>
      <button type="button" class="avatar-random small-button">随机配色</button><p class="avatar-caption">保存后会同步到你的阵容和作者主页。</p></div></div>
      <footer class="avatar-editor-footer"><p id="avatarFeedback" role="status" aria-live="polite"></p><div><button type="button" class="small-button avatar-cancel">取消</button><button type="submit" class="small-button avatar-save">保存头像</button></div></footer>
    </form>`;
    document.body.append(dialog);
    const form = dialog.querySelector('form');
    const picker = dialog.querySelector('#avatarColor');
    const hex = dialog.querySelector('#avatarHex');
    const feedback = dialog.querySelector('#avatarFeedback');
    const save = dialog.querySelector('.avatar-save');
    let saved = user.avatar_color;
    let draft = saved;
    let busy = false;
    const palettes = Object.values(window.jccAvatar.palettes);
    const swatches = palettes.map(palette => {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'avatar-swatch';
      button.style.setProperty('--swatch', palette.mid);
      button.setAttribute('aria-label', palette.name);
      button.title = palette.name;
      button.addEventListener('click', () => update(palette.mid));
      dialog.querySelector('.avatar-swatches').append(button);
      return button;
    });
    function update(color) {
      draft = color.toLowerCase(); picker.value = draft; hex.value = draft;
      hex.setCustomValidity(''); feedback.textContent = draft === saved ? '当前头像' : '预览中 · 尚未保存';
      dialog.querySelector('#avatarLargePreview').replaceChildren(window.jccAvatar.image(draft, 176, '头像实时预览'));
      dialog.querySelector('.avatar-size-preview').replaceChildren(window.jccAvatar.image(draft, 40), window.jccAvatar.image(draft, 28));
      swatches.forEach((button, index) => button.setAttribute('aria-pressed', String(palettes[index].mid === draft)));
      save.disabled = draft === saved;
    }
    picker.addEventListener('input', () => update(picker.value));
    hex.addEventListener('input', () => {
      if (/^#[0-9a-f]{6}$/i.test(hex.value)) update(hex.value);
      else { hex.setCustomValidity('请输入 # 加六位十六进制颜色'); save.disabled = true; feedback.textContent = '请输入完整颜色，例如 #7c3aed'; }
    });
    dialog.querySelector('.avatar-random').addEventListener('click', () => {
      const options = palettes.filter(p => p.mid !== draft);
      update(options[Math.floor(Math.random() * options.length)].mid);
    });
    function close() { if (!busy) dialog.close(); }
    dialog.querySelector('.avatar-close').addEventListener('click', close);
    dialog.querySelector('.avatar-cancel').addEventListener('click', close);
    dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
    section.querySelector('#editAvatar').addEventListener('click', () => { update(saved); dialog.showModal(); });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (busy || !form.reportValidity() || draft === saved) return;
      busy = true;
      const controls = [...form.querySelectorAll('button, input')];
      controls.forEach(control => { control.disabled = true; });
      feedback.textContent = '正在保存…';
      try {
        const response = await fetch('/api/me/avatar', { method: 'PUT', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken}, body: JSON.stringify({color: draft}) });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || '保存失败，请重试');
        saved = payload.user.avatar_color;
        savedImage.src = window.jccAvatar.getAvatarDataUrl('', {color: saved, size: 80});
        section.querySelector('.avatar-caption').textContent = '头像已更新，新的色彩已同步';
        dialog.close();
      } catch (error) { feedback.textContent = error.message || '网络异常，请重试'; }
      finally { busy = false; controls.forEach(control => { control.disabled = false; }); save.disabled = draft === saved; }
    });
    if (location.hash === '#avatar') section.querySelector('#editAvatar').click();
  }
  window.jccAvatarEditor = {mount};
})();
