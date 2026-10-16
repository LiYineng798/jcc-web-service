import * as React from 'react';
import { createRoot } from 'react-dom/client';
import { createPortal } from 'react-dom';
import { AnimatedIcon, type IconMotion } from '@/components/ui/animated-icon';

const calmIcons = new Set(['flag', 'eye-off', 'pencil']);
const container = document.getElementById('lineupList');
if (container) {
  const host = document.createElement('div');
  host.id = 'homeCardIcons';
  container.after(host);
  const root = createRoot(host);
  let slots: HTMLElement[] = [];
  let signatures: string[] = [];
  const sync = () => {
    const next = Array.from(container.querySelectorAll<HTMLElement>('.home-lineup-card [data-card-icon]'));
    const keys = next.map(slot => `${slot.dataset.cardIcon}:${slot.dataset.iconPreset || 'auto'}`);
    if (next.length === slots.length && next.every((slot, i) => slot === slots[i] && keys[i] === signatures[i])) return;
    slots = next;
    signatures = keys;
    root.render(<>{slots.map((slot, index) => createPortal(
      <AnimatedIcon name={slot.dataset.cardIcon!}
        preset={(slot.dataset.iconPreset || (calmIcons.has(slot.dataset.cardIcon!) ? 'pulse' : 'auto')) as IconMotion}
        amplitude={calmIcons.has(slot.dataset.cardIcon!) ? 0.35 : 0.7}
        duration={calmIcons.has(slot.dataset.cardIcon!) ? 0.5 : 0.48}
        ease={calmIcons.has(slot.dataset.cardIcon!) ? 'linear' : 'gentle'} />,
      slot, `${slot.closest<HTMLElement>('[data-lineup-key]')?.dataset.lineupKey}:${index}`,
    ))}</>);
  };
  const observer = new MutationObserver(sync);
  observer.observe(container, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-card-icon', 'data-icon-preset'] });
  sync();
  window.addEventListener('pagehide', event => {
    if (event.persisted) return;
    observer.disconnect();
    root.unmount();
    host.remove();
  }, { once: true });
}
