import { createRoot, type Root } from 'react-dom/client';
import { MotionConfig } from 'framer-motion';
import { InteractiveLogsTable } from '@/components/ui/interactive-logs-table-shadcnui';
import './audit-ui.css';

let root: Root | undefined;
export function mount(element: HTMLElement) {
  unmount();
  root = createRoot(element);
  root.render(<MotionConfig reducedMotion="user"><InteractiveLogsTable /></MotionConfig>);
}
export function unmount() { root?.unmount(); root = undefined; }
