import type { ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost';

const variantClass: Record<Variant, string> = {
  primary: 'bg-button text-button-text hover:opacity-90',
  secondary: 'bg-secondary text-text hover:opacity-90',
  ghost: 'bg-transparent text-link hover:opacity-90',
};

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export function Button({ variant = 'primary', className = '', ...rest }: Props) {
  return (
    <button
      {...rest}
      className={`rounded px-4 py-2 text-sm font-medium transition disabled:opacity-50 ${variantClass[variant]} ${className}`}
    />
  );
}
