import { ChevronRightIcon } from './icons';

interface SectionAction {
  label: string;
  onClick: () => void;
}

interface Props {
  title: string;
  count?: number;
  action?: SectionAction;
}

export function SectionHead({ title, count, action }: Props) {
  return (
    <div className="tf-sectionhead">
      <h2>
        {title}
        {count != null ? <span className="count">{count}</span> : null}
      </h2>
      {action ? (
        <button type="button" className="link" onClick={action.onClick}>
          {action.label}
          <ChevronRightIcon size={11} />
        </button>
      ) : null}
    </div>
  );
}
