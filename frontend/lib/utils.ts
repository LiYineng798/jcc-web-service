import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }

// After a page change, bring the list start back under the admin top bar.
// Mirrors JccAdminCore.revealListStart for the React admin workspaces.
export function revealListStart(node: HTMLElement | null) {
  if (!node?.isConnected) return;
  const header = document.querySelector('.admin-topbar')?.getBoundingClientRect().bottom || 0;
  const offset = node.getBoundingClientRect().top - header - 12;
  if (offset >= 0) return;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  window.scrollBy({ top: offset, behavior: reduceMotion ? 'auto' : 'smooth' });
}
