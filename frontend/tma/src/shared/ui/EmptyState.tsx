import type { ReactNode } from 'react';

interface Props {
  icon: ReactNode;
  title: string;
  body: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({ icon, title, body, actionLabel, onAction }: Props) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-3 flex h-20 w-20 items-center justify-center rounded-full bg-link/10 text-link">
        <span className="block [&_svg]:h-10 [&_svg]:w-10">{icon}</span>
      </div>
      <h3 className="mb-1.5 text-base font-semibold">{title}</h3>
      <p className="mb-4 max-w-sm text-sm leading-relaxed text-hint">{body}</p>
      {actionLabel ? (
        <button
          type="button"
          onClick={onAction}
          className="rounded-full bg-button px-5 py-3 text-sm font-semibold text-button-text active:opacity-90"
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
