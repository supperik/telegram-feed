import type { ReactNode } from 'react';
import { ArrowUpRightIcon } from './icons';

interface Props {
  icon: ReactNode;
  title: string;
  body: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({ icon, title, body, actionLabel, onAction }: Props) {
  return (
    <div className="tf-empty">
      <div className="icon">{icon}</div>
      <h3>{title}</h3>
      <p>{body}</p>
      {actionLabel ? (
        <button type="button" className="cta" onClick={onAction}>
          {actionLabel}
          <ArrowUpRightIcon size={14} />
        </button>
      ) : null}
    </div>
  );
}
