import type { ReactNode } from 'react';

interface Props {
  title: string;
  // The back affordance — pass a <Link className="back"> so it routes.
  back: ReactNode;
}

export function SubHeader({ title, back }: Props) {
  return (
    <header className="tf-subhead">
      {back}
      <h2>{title}</h2>
    </header>
  );
}
