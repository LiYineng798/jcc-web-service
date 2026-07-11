(function initHomeTransitions(global) {
  'use strict';

  function numberVariable(root, name, fallback) {
    const value = parseFloat(global.getComputedStyle(root).getPropertyValue(name));
    return Number.isFinite(value) ? value : fallback;
  }

  function timeVariable(root, name, fallback) {
    const raw = global.getComputedStyle(root).getPropertyValue(name).trim();
    if (!raw) return fallback;
    const value = parseFloat(raw);
    if (!Number.isFinite(value)) return fallback;
    return raw.endsWith('s') && !raw.endsWith('ms') ? value * 1000 : value;
  }

  function easeOutQuint(progress) {
    return 1 - Math.pow(1 - progress, 5);
  }

  function easeInOut(progress) {
    return progress < 0.5
      ? 2 * progress * progress
      : 1 - Math.pow(-2 * progress + 2, 2) / 2;
  }

  function createGlowLayers(root, input, value, progress) {
    if (!value) return '';
    const style = global.getComputedStyle(input);
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    if (!context) return '';
    context.font = style.font;

    const paddingLeft = parseFloat(style.paddingLeft) || 0;
    const inputWidth = input.clientWidth;
    const spread = numberVariable(root, '--glow-spread', 1.5);
    const peakAt = numberVariable(root, '--glow-peak-at', 0.15);
    const words = value.match(/\S+|\s+/g) || [];
    let cursor = paddingLeft;
    const rise = Math.min(1, progress / Math.max(peakAt, 0.01));
    const fall = progress <= peakAt ? 1 : 1 - ((progress - peakAt) / Math.max(1 - peakAt, 0.01));
    const strength = Math.max(0, Math.min(rise, fall));
    const vertical = 72 - progress * 54;
    const layers = [];

    words.forEach((word) => {
      const width = context.measureText(word).width;
      if (word.trim()) {
        const center = Math.max(0, Math.min(inputWidth, cursor + width / 2));
        const radius = Math.max(18, width * spread);
        layers.push(
          `radial-gradient(ellipse ${radius.toFixed(1)}px 24px at ${center.toFixed(1)}px ${vertical.toFixed(1)}%, rgba(201, 100, 66, ${(strength * 0.72).toFixed(3)}) 0%, rgba(201, 100, 66, ${(strength * 0.28).toFixed(3)}) 38%, transparent 72%)`
        );
      }
      cursor += width;
    });
    return layers.join(', ');
  }

  function createSearchClear({ root, input, mirror, placeholder, glow, button, onClear }) {
    const reducedMotion = global.matchMedia('(prefers-reduced-motion: reduce)');
    let frameId = 0;
    let startedAt = 0;

    function clearStyles() {
      mirror.removeAttribute('style');
      placeholder.removeAttribute('style');
      glow.removeAttribute('style');
    }

    function sync(value = input.value) {
      const hasValue = Boolean(value);
      if (!root.classList.contains('is-clearing')) mirror.textContent = value;
      root.classList.toggle('has-value', hasValue);
      button.disabled = !hasValue || input.disabled;
    }

    function cancel() {
      if (frameId) global.cancelAnimationFrame(frameId);
      frameId = 0;
      root.classList.remove('is-clearing');
      clearStyles();
      sync();
    }

    function finish() {
      frameId = 0;
      root.classList.remove('is-clearing');
      mirror.textContent = '';
      clearStyles();
      sync('');
    }

    function animate(timestamp) {
      if (!startedAt) startedAt = timestamp;
      const duration = timeVariable(root, '--clear-dur', 1000);
      const progress = Math.min(1, (timestamp - startedAt) / Math.max(duration, 1));
      const easedOut = easeOutQuint(Math.min(1, progress / 0.58));
      const placeholderProgress = easeInOut(Math.max(0, (progress - 0.28) / 0.5));
      const outFly = numberVariable(root, '--clear-out-fly', 12);
      const inFly = numberVariable(root, '--clear-in-fly', 12);
      const blur = numberVariable(root, '--clear-blur', 2);
      const glowOpacity = numberVariable(root, '--glow-opacity', 0.42);

      mirror.style.transform = `translateY(${-outFly * easedOut}px)`;
      mirror.style.opacity = String(1 - easedOut);
      mirror.style.filter = `blur(${blur * easedOut}px)`;
      placeholder.style.transform = `translateY(${inFly * (1 - placeholderProgress)}px)`;
      placeholder.style.opacity = String(placeholderProgress);
      placeholder.style.filter = `blur(${blur * (1 - placeholderProgress)}px)`;
      glow.style.background = createGlowLayers(root, input, mirror.textContent, progress);
      glow.style.opacity = String(glowOpacity * Math.sin(Math.PI * progress));

      if (progress >= 1) {
        finish();
        return;
      }
      frameId = global.requestAnimationFrame(animate);
    }

    function clear() {
      const oldValue = input.value;
      if (!oldValue || input.disabled) return;
      cancel();
      mirror.textContent = oldValue;
      input.value = '';
      root.classList.remove('has-value');
      button.disabled = true;
      onClear();
      if (reducedMotion.matches) {
        finish();
        return;
      }
      root.classList.add('is-clearing');
      startedAt = 0;
      frameId = global.requestAnimationFrame(animate);
    }

    function setDisabled(disabled, placeholderText) {
      cancel();
      input.disabled = disabled;
      if (placeholderText) {
        root.dataset.placeholder = placeholderText;
        placeholder.textContent = placeholderText;
      }
      sync();
    }

    button.addEventListener('click', clear);
    sync();

    return {
      sync,
      setDisabled,
      cancel,
      destroy() {
        cancel();
        button.removeEventListener('click', clear);
      },
    };
  }

  function createLineupLoader({ container, count = 3 }) {
    let wrapper = null;

    function createSkeletonCard() {
      const card = document.createElement('article');
      card.className = 'lineup-card t-skel-card';
      ['title', 'meta', 'code'].forEach((kind) => {
        const block = document.createElement('span');
        block.className = `t-skel-block t-skel-${kind}`;
        card.append(block);
      });
      const actions = document.createElement('div');
      actions.className = 't-skel-actions';
      for (let index = 0; index < 5; index += 1) {
        const action = document.createElement('span');
        action.className = 't-skel-block t-skel-action';
        actions.append(action);
      }
      card.append(actions);
      return card;
    }

    function createWrapper(withSkeletons) {
      wrapper = document.createElement('div');
      wrapper.className = 't-skel';
      const skeleton = document.createElement('div');
      skeleton.className = 't-skel-skeleton is-pulsing';
      if (withSkeletons) {
        for (let index = 0; index < count; index += 1) skeleton.append(createSkeletonCard());
      }
      const content = document.createElement('div');
      content.className = 't-skel-content';
      wrapper.append(skeleton, content);
      return wrapper;
    }

    function showLoading() {
      const nextWrapper = createWrapper(true);
      container.replaceChildren(nextWrapper);
    }

    function reveal(nodes, options = {}) {
      if (!nodes.length) {
        container.replaceChildren();
        wrapper = null;
        return;
      }
      if (!wrapper || !container.contains(wrapper)) {
        const nextWrapper = createWrapper(false);
        nextWrapper.classList.add('is-resetting');
        container.replaceChildren(nextWrapper);
      }
      const content = wrapper.querySelector('.t-skel-content');
      content.replaceChildren(...nodes);
      if (!options.animate) {
        wrapper.classList.add('is-resetting', 'is-revealed');
        void wrapper.offsetWidth;
        wrapper.classList.remove('is-resetting');
        return;
      }
      wrapper.classList.add('is-resetting');
      wrapper.classList.remove('is-revealed');
      void wrapper.offsetWidth;
      wrapper.classList.remove('is-resetting');
      global.requestAnimationFrame(() => {
        if (wrapper && container.contains(wrapper)) wrapper.classList.add('is-revealed');
      });
    }

    function fail() {
      if (wrapper && container.contains(wrapper) && !wrapper.classList.contains('is-revealed')) {
        container.replaceChildren();
      }
      wrapper = null;
    }

    function reset() {
      container.replaceChildren();
      wrapper = null;
    }

    return { showLoading, reveal, fail, reset };
  }

  global.JccHomeTransitions = {
    createSearchClear,
    createLineupLoader,
  };
})(window);
