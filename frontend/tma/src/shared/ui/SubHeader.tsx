import { ChevronLeftIcon } from './icons';

interface Props {
  title: string;
  onBack: () => void;
}

export function SubHeader({ title, onBack }: Props) {
  return (
    <header className="tf-subhead">
      <button type="button" className="back" aria-label="Назад" onClick={onBack}>
        <ChevronLeftIcon size={16} />
      </button>
      <h2>{title}</h2>
    </header>
  );
}
