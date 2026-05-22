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
  return (
    <div className="tf-pillgroup">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          className="tf-pill"
          data-active={t.id === active}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
