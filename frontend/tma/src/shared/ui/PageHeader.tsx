import type { ReactNode } from 'react';
import { RefreshIcon } from './icons';

interface Props {
  title: string;
  subtitle?: ReactNode;
  onRefresh?: () => void;
  refreshing?: boolean;
}

export function PageHeader({ title, subtitle, onRefresh, refreshing = false }: Props) {
  return (
    <header className="tf-pageheader">
      <div>
        <h1>{title}</h1>
        {subtitle != null ? <div className="subtitle">{subtitle}</div> : null}
      </div>
      {onRefresh ? (
        <button
          type="button"
          className="tf-iconbtn"
          aria-label="Обновить"
          onClick={onRefresh}
          disabled={refreshing}
        >
          <RefreshIcon size={16} className={refreshing ? 'tf-spin' : undefined} />
        </button>
      ) : null}
    </header>
  );
}
