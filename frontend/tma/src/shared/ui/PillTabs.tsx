import type { CSSProperties } from 'react';

interface PillTab {
  id: string;
  label: string;
}

interface Props {
  tabs: PillTab[];
  active: string;
  onChange: (id: string) => void;
}

export function PillTabs({ tabs, active, onChange }: Props) {
  const activeIdx = Math.max(0, tabs.findIndex((t) => t.id === active));
  // CSS custom props drive the sliding indicator — same approach as the
  // bottom-nav tab pill, so both animate identically.
  const indicatorStyle: CSSProperties & Record<string, string | number> = {
    '--idx': activeIdx,
    '--count': tabs.length,
  };
  return (
    <div className="tf-pillgroup">
      <div className="tf-pill-indicator" style={indicatorStyle} />
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          className="tf-pill"
          data-active={t.id === active}
          aria-pressed={t.id === active}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
