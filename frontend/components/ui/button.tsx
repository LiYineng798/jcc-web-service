import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'outline' | 'ghost' | 'default' }>(
  ({ className, variant = 'outline', type = 'button', ...props }, ref) =>
    <button ref={ref} type={type} className={cn('al-button', 'al-button-' + variant, className)} {...props} />
);
Button.displayName = 'Button';
