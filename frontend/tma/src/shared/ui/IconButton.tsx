import type { ButtonHTMLAttributes } from 'react';

type Variant = 'default' | 'danger';

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: number;
}

const variantClass: Record<Variant, string> = {
  default: 'bg-black/5 text-hint hover:text-text active:bg-black/10',
  danger: 'bg-danger/10 text-danger active:bg-danger/20',
};

export function IconButton({
  variant = 'default',
  size = 36,
  className = '',
  children,
  ...rest
}: Props) {
  return (
    <button
      type="button"
      {...rest}
      style={{ width: `${size}px`, height: `${size}px`, ...(rest.style ?? {}) }}
      className={`inline-flex shrink-0 items-center justify-center rounded-full transition disabled:opacity-40 ${variantClass[variant]} ${className}`}
    >
      {children}
    </button>
  );
}
