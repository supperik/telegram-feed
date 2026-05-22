import type { ReactNode } from 'react';

interface Props {
  title: string;
  count?: number;
  // A pill-styled link/button — pass an element with className="link".
  action?: ReactNode;
}

export function SectionHead({ title, count, action }: Props) {
  return (
    <div className="tf-sectionhead">
      <h2>
        {title}
        {count != null ? <span className="count">{count}</span> : null}
      </h2>
      {action ?? null}
    </div>
  );
}
