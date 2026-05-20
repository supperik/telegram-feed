import { Link } from '@tanstack/react-router';
import { HiddenSourceListItem } from '@/features/sources/HiddenSourceListItem';
import { useHiddenSources } from '@/features/sources/useHiddenSources';
import { Spinner } from '@/shared/ui/Spinner';

export function HiddenSourcesScreen() {
  const hidden = useHiddenSources();
  const items = hidden.data?.items ?? [];

  return (
    <div>
      <header className="flex items-center gap-2 px-4 pt-3 pb-2">
        <Link to="/sources" className="text-link text-sm">
          ← К источникам
        </Link>
        <h1 className="ml-1 text-base font-semibold">Скрыты из ленты</h1>
      </header>

      {hidden.status === 'pending' ? (
        <div className="flex items-center justify-center py-6">
          <Spinner />
        </div>
      ) : items.length === 0 ? (
        <div className="mx-3 rounded-2xl bg-secondary px-4 py-8 text-center text-xs text-hint">
          Нет скрытых каналов.
        </div>
      ) : (
        <ul className="mx-3 overflow-hidden rounded-2xl bg-secondary shadow-card">
          {items.map((i) => (
            <HiddenSourceListItem key={i.channel.id} item={i} />
          ))}
        </ul>
      )}
    </div>
  );
}
