/* Keep generated PNGs available even when a mobile browser blocks downloads. */
(() => {
  'use strict';
  let current = null;
  const dialog = document.createElement('dialog');
  dialog.className = 'creator-save-dialog';
  dialog.setAttribute('aria-labelledby', 'poster-save-title');
  dialog.innerHTML = `<header><div><p>READY TO SAVE · PNG</p><h2 id="poster-save-title">海报已生成</h2></div><button type="button" class="creator-secondary" data-save-close>返回编辑</button></header>
    <p class="poster-save-status" role="status">点击保存按钮，或长按下方图片保存到相册。</p>
    <div class="poster-save-actions"><button type="button" class="creator-primary" data-save-share hidden>保存 / 分享图片</button><a class="creator-secondary" data-save-download>下载 PNG</a><a class="creator-secondary" data-save-open target="_blank" rel="noopener">打开原图</a></div>
    <img class="poster-save-image" alt="已生成的完整海报，可长按保存">`;
  document.body.append(dialog);
  const status = dialog.querySelector('[role="status"]');
  const share = dialog.querySelector('[data-save-share]');
  const download = dialog.querySelector('[data-save-download]');
  const full = dialog.querySelector('[data-save-open]');
  const preview = dialog.querySelector('img');
  dialog.querySelector('[data-save-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => document.getElementById('export-poster')?.focus({preventScroll:true}));
  // Retain the URL after closing: an in-flight download or opened tab may still use it.
  // Release the previous result on replacement; the browser releases all URLs on unload.
  share.addEventListener('click', async () => {
    if (!current || share.disabled) return;
    share.disabled = true;
    try {
      // Call directly from this new gesture, without asynchronous work before share().
      await navigator.share({files: [current.file]});
      status.textContent = '图片已交给系统，请在所选应用中确认保存。';
    } catch (error) {
      status.textContent = error.name === 'AbortError'
        ? '已取消分享，海报仍在这里，可以重新保存。'
        : '此浏览器暂时无法分享文件。请长按下方图片保存，或打开原图后保存。';
    } finally { share.disabled = false; }
  });
  download.addEventListener('click', () => {
    status.textContent = '已请求下载；若没有出现文件，请长按图片保存，或使用“打开原图”。';
  });
  window.JccPosterSave = {
    present(blob, filename) {
      if (!(blob instanceof Blob) || !blob.size) throw new Error('海报生成失败，请重试');
      const previous = current;
      const url = URL.createObjectURL(blob);
      const file = typeof File === 'function' ? new File([blob], filename, {type: 'image/png'}) : null;
      current = {url, file};
      preview.src = full.href = download.href = url;
      download.download = filename;
      let canShare = false;
      try { canShare = Boolean(file && navigator.share && navigator.canShare?.({files: [file]})); } catch { /* Use image fallback. */ }
      share.hidden = !canShare;
      status.textContent = canShare
        ? '点击“保存 / 分享图片”选择存储位置；也可以长按下方图片保存到相册。'
        : '点击“下载 PNG”，或长按下方图片保存。微信等内置浏览器也可尝试打开原图。';
      if (!dialog.open) dialog.showModal();
      // Desktop retains the one-click download, with the same visible retry fallback.
      if (!matchMedia('(pointer: coarse)').matches && !/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) download.click();
      if (previous) setTimeout(() => URL.revokeObjectURL(previous.url), 60000);
    },
  };
})();
