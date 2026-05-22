import type { ButtonHTMLAttributes } from 'react';

type Variant = 'default' | 'danger';

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: number;
}

export function IconButton({
  variant = 'default',
  size = 38,
  className = '',
  style,
  children,
  ...rest
}: Props) {
  return (
    <button
      type="button"
      {...rest}
      data-variant={variant}
      style={{ width: size, height: size, ...style }}
      className={`tf-iconbtn ${className}`.trim()}
    >
      {children}
    </button>
  );
}
