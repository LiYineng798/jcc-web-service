// SPDX-License-Identifier: AGPL-3.0-only
import { createAvatar, type AvatarController } from '@bible-strong/avatar-web';
import { renderAvatarDefinition, type AvatarDefinition, type AvatarExpressionDefinition } from '@bible-strong/avatar-core';
import bundled from './avatar-presets.json';

export type AvatarConfig = { version: 1; preset: string; expression: string; color: string };
export const presets = {
  strobi: { name: '团团 · Strobi', recommended: ['blue', 'rose', 'monochrome'] },
  freddy: { name: '小熊 · Freddy', recommended: ['monochrome', 'amber', 'indigo'] },
  citrus: { name: '柚子 · Citrus', recommended: ['amber', 'emerald', 'sky'] },
  nova: { name: '新星 · Nova', recommended: ['purple', 'blue', 'indigo'] },
  sunee: { name: '暖阳 · Sunee', recommended: ['amber', 'rose', 'monochrome'] },
  cloudee: { name: '浮云 · Cloudee', recommended: ['blue', 'sky', 'purple'] },
  sprout: { name: '新芽 · Sprout', recommended: ['emerald', 'sky', 'monochrome'] },
  bloom: { name: '花语 · Bloom', recommended: ['rose', 'purple', 'amber'] },
};
export const expressions = {
  neutral: { name: '自然' }, happy: { name: '开心' }, wink: { name: '俏皮' }, sleepy: { name: '慵懒' },
  curious: { name: '好奇' }, surprised: { name: '惊讶' }, shy: { name: '害羞' }, determined: { name: '酷酷' },
};
export const palettes = {
  amber: { mid: '#d5a06f', name: '陶杏' }, emerald: { mid: '#7e927d', name: '苔绿' },
  blue: { mid: '#7e96ad', name: '雾蓝' }, purple: { mid: '#9b8ba5', name: '烟紫' },
  rose: { mid: '#b98187', name: '豆沙' }, monochrome: { mid: '#b8a48d', name: '砂岩' },
  sky: { mid: '#6f9893', name: '青瓷' }, indigo: { mid: '#66717e', name: '石墨' },
};
const has = (object: object, key: unknown): key is string => typeof key === 'string' && Object.hasOwn(object, key);
const hex = (value: unknown) => typeof value === 'string' && /^#[a-f\d]{6}$/i.test(value);
export function normalize(input: unknown): AvatarConfig {
  const value = input && typeof input === 'object' ? input as Record<string, unknown> : { color: input };
  return {
    version: 1,
    preset: has(presets, value.preset) ? value.preset : 'strobi',
    expression: has(expressions, value.expression) ? value.expression : 'neutral',
    color: hex(value.color) ? (value.color as string).toLowerCase() : '#7e96ad',
  };
}
function eyeColor(color: string): `#${string}` {
  const rgb = [1, 3, 5].map(i => parseInt(color.slice(i, i + 2), 16) / 255)
    .map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
  return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722 > .22 ? '#161923' : '#ffffff';
}
function expression(value: Record<string, number | string>): AvatarExpressionDefinition {
  return {
    head: { x: Number(value.headX || 0), y: Number(value.headY || 0), z: Number(value.headZ || 0) },
    eyes: {
      left: { width: Number(value.widthLeft), height: Number(value.heightLeft), x: Number(value.positionXLeft), y: Number(value.positionYLeft), angle: Number(value.leftAngle) },
      right: { width: Number(value.widthRight), height: Number(value.heightRight), x: Number(value.positionXRight), y: Number(value.positionYRight), angle: Number(value.rightAngle) },
      spacing: Number(value.spacing),
    },
    perspective: 1, motion: { eyes: 'none', body: 'none' },
  };
}
function definition(config: AvatarConfig): AvatarDefinition {
  const preset = bundled.presets[config.preset as keyof typeof bundled.presets];
  const faces: Record<string, AvatarExpressionDefinition> = { neutral: expression(preset.eyes) };
  for (const [name, value] of Object.entries(bundled.expressions)) faces[name] = expression(value);
  faces.copied = { ...faces.wink, head: { x: 9, y: -10, z: -14 } };
  faces.liked = { ...faces.happy, head: { x: -9, y: 6, z: 10 } };
  faces.favorited = { ...faces.happy, head: { x: -5, y: -9, z: -8 },
    eyes: { ...faces.happy.eyes, spacing: 46,
      left: { width: 27, height: 42, x: 0, y: -4, angle: 12 },
      right: { width: 27, height: 42, x: 0, y: -4, angle: -12 } } };
  return {
    schema: 'bible-strong/avatar-definition', schemaVersion: 1,
    body: preset.body as AvatarDefinition['body'],
    colors: { body: config.color as `#${string}`, eyes: eyeColor(config.color) },
    expressions: faces, expressionOrder: Object.keys(faces), animations: {}, animationOrder: [],
  };
}
function viewport(config: AvatarConfig): string {
  return bundled.presets[config.preset as keyof typeof bundled.presets].viewport.join(' ');
}
const svgCache = new Map<string, string>();
function dataUrl(config: AvatarConfig, face = config.expression): string {
  const key = JSON.stringify([config.preset, config.color, face]);
  const cached = svgCache.get(key);
  if (cached) { svgCache.delete(key); svgCache.set(key, cached); return cached; }
  const { geometry: g, colors } = renderAvatarDefinition(definition(config), face);
  const body = (paths: readonly string[]) => paths.map(d => `<path d="${d}" fill="${colors.body}"/>`).join('');
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewport(config)}" width="300" height="300"><defs><clipPath id="face"><path d="${g.headPath}"/></clipPath></defs>${body(g.backPaths)}${body([g.headPath])}<g clip-path="url(#face)" fill="${colors.eyes}"><path d="${g.leftPath}" opacity="${g.leftVisible ? 1 : 0}"/><path d="${g.rightPath}" opacity="${g.rightVisible ? 1 : 0}"/></g>${body(g.frontPaths)}</svg>`;
  const result = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  svgCache.set(key, result);
  if (svgCache.size > 128) svgCache.delete(svgCache.keys().next().value!);
  return result;
}
export function getAvatarDataUrl(_seed = '', options: { config?: unknown; color?: string; size?: number; palette?: string } = {}): string {
  const color = options.color || (has(palettes, options.palette) ? palettes[options.palette as keyof typeof palettes].mid : undefined);
  return dataUrl(normalize(options.config || color));
}
type FeedbackKind = 'copy' | 'like' | 'favorite';
type Model = {
  node: HTMLElement; config: AvatarConfig; size: number; alt: string; key?: string;
  controller?: AvatarController; timer?: ReturnType<typeof setTimeout>; settle?: ReturnType<typeof setTimeout>;
  motion?: Animation[];
};
const models = new WeakMap<HTMLElement, Model>();
const active = new Set<Model>();
const keyed = new Map<string, Model>();
let removals: MutationObserver | undefined;
const motionPreference = window.matchMedia?.('(prefers-reduced-motion: reduce)');
const reducedMotion = () => motionPreference?.matches ?? false;
motionPreference?.addEventListener('change', event => {
  if (event.matches) for (const model of active) finish(model);
});
function paintStatic(model: Model, face = model.config.expression) {
  const img = document.createElement('img');
  img.width = model.size; img.height = model.size; img.alt = model.alt;
  img.style.cssText = 'display:block;width:100%;height:100%;object-fit:contain';
  img.src = dataUrl(model.config, face);
  model.node.replaceChildren(img);
  model.node.dataset.avatarExpression = face;
}
function clearEmphasis(model: Model) {
  model.motion?.forEach(animation => animation.cancel());
  model.motion = undefined;
}
function emphasize(model: Model, kind: FeedbackKind) {
  const visual = model.node.firstElementChild;
  const continuing = model.motion?.some(animation => animation.playState === 'running' || animation.playState === 'paused');
  const current = visual && continuing ? getComputedStyle(visual).transform : null;
  clearEmphasis(model);
  if (!visual) return;
  if (reducedMotion() || !visual.animate) return;
  const poses = {
    copy: ['scale(1)', 'translateY(1px) rotate(-6deg) scale(.96)', 'translateY(-2px) rotate(5deg) scale(1.32)', 'rotate(-2deg) scale(1.14)', 'scale(1)'],
    like: ['scale(1)', 'translateY(1px) scale(.92)', 'translateY(-5px) rotate(-5deg) scale(1.42)', 'translateY(-2px) rotate(2deg) scale(1.22)', 'scale(1)'],
    favorite: ['scale(1)', 'rotate(-6deg) scale(1.08)', 'translateY(-3px) rotate(4deg) scale(1.36)', 'translateY(-2px) scale(1.24)', 'scale(1)'],
  };
  const frames = current && current !== 'none' ? [current, ...poses[kind].slice(2)] : poses[kind];
  const offsets = frames.length === 4 ? [0, .28, .55, 1] : [0, .12, .3, .55, 1];
  model.motion = [
    visual.animate(frames.map((transform, i) => ({ transform, offset: offsets[i], easing: 'cubic-bezier(.22,.72,.24,1)' })),
      { duration: kind === 'copy' ? 820 : 1100, easing: 'linear' }),
  ];
}
function finish(model: Model) {
  clearTimeout(model.timer); clearTimeout(model.settle);
  clearEmphasis(model);
  model.controller?.destroy(); model.controller = undefined;
  paintStatic(model);
  model.node.classList.remove('is-reacting');
  delete model.node.dataset.avatarFeedback;
  active.delete(model);
  if (model.key && keyed.get(model.key) === model) keyed.delete(model.key);
  if (!active.size) { removals?.disconnect(); removals = undefined; }
}
export function image(input: unknown, size = 36, alt = '', key?: string): HTMLElement {
  const config = normalize(input);
  size = Number.isFinite(size) ? Math.max(16, Math.min(512, size)) : 36;
  const current = key ? keyed.get(key) : undefined;
  // Card refreshes reparent the active node rather than restarting its transition.
  if (current && JSON.stringify(current.config) === JSON.stringify(config) && current.size === size && current.alt === alt) return current.node;
  if (current) finish(current);
  const node = document.createElement('span');
  node.className = 'user-avatar';
  node.dataset.avatarPreset = config.preset;
  node.style.cssText = `display:inline-block;flex-shrink:0;width:${size}px;height:${size}px;vertical-align:middle`;
  const model = { node, config, size, alt, key };
  models.set(node, model);
  paintStatic(model);
  return node;
}
export function feedback(node: HTMLElement | null, kind: FeedbackKind = 'copy'): void {
  if (!node || !node.isConnected || document.hidden) return;
  const model = models.get(node);
  if (!model) return;
  const face = { copy: 'copied', like: 'liked', favorite: 'favorited' }[kind];
  if (!face) return;
  clearTimeout(model.timer); clearTimeout(model.settle);
  node.dataset.avatarFeedback = kind;
  node.dataset.avatarExpression = face;
  node.classList.add('is-reacting');
  active.add(model);
  if (model.key) keyed.set(model.key, model);
  try {
    if (reducedMotion()) {
      model.controller?.destroy(); model.controller = undefined;
      paintStatic(model, face);
    } else {
      if (!model.controller) {
        const mount = document.createElement('span');
        model.controller = createAvatar(mount, {
          definition: definition(model.config), defaultExpression: model.config.expression,
          autoplay: false, size: '100%', ariaLabel: model.alt || '用户头像',
        });
        // Match the still-image artboard so switching to live SVG cannot resize the character.
        mount.querySelector('svg')?.setAttribute('viewBox', viewport(model.config));
        node.replaceChildren(mount);
        mount.style.cssText = 'display:block;width:100%;height:100%';
      }
      // Re-selecting the current expression interrupts the runtime's in-flight morph.
      if (model.controller.getState().activeExpression !== face) model.controller.setExpression(face);
    }
  } catch (error) {
    model.controller?.destroy(); model.controller = undefined;
    paintStatic(model, face);
    console.warn('Avatar motion fell back to a still expression.', error);
  }
  emphasize(model, kind);
  model.timer = setTimeout(() => {
    if (!model.controller || reducedMotion() || !node.isConnected) { finish(model); return; }
    node.dataset.avatarExpression = model.config.expression;
    model.controller.setExpression(model.config.expression);
    model.settle = setTimeout(() => finish(model), 460);
  }, 1700);
  if (!removals) {
    removals = new MutationObserver(() => {
      for (const item of active) if (!item.node.isConnected) finish(item);
    });
    removals.observe(document.body, { childList: true, subtree: true });
  }
}
function dispose(root: Element) {
  for (const model of active) if (root === model.node || root.contains(model.node)) finish(model);
}
document.addEventListener('visibilitychange', () => {
  if (document.hidden) for (const model of active) finish(model);
});
Object.assign(window, { jccAvatar: { image, getAvatarDataUrl, normalize, presets, expressions, palettes, feedback, dispose } });
