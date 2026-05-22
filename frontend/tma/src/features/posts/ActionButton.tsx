import { useState, type ButtonHTMLAttributes, type ReactNode } from 'react';

interface Props extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onClick'> {
  icon: ReactNode;
  label?: string;
  on?: boolean;
  onClick?: () => void;
}

// Post-footer action button — icon + optional label, with a tap burst/flash
// animation re-keyed on every press so the CSS animation restarts.
export function ActionButton({ icon, label, on = false, onClick, className = '', ...rest }: Props) {
  const [tapped, setTapped] = useState(0);
  return (
    <button
      type="button"
      {...rest}
      data-on={on}
      onClick={() => {
        setTapped((v) => v + 1);
        onClick?.();
      }}
      className={`tf-action ${className}`.trim()}
    >
      {tapped > 0 ? <span key={tapped} className="tf-action-flash" aria-hidden="true" /> : null}
      <span key={`burst-${tapped}`} className="tf-action-burst">
        {icon}
      </span>
      {label ? <span>{label}</span> : null}
    </button>
  );
}
