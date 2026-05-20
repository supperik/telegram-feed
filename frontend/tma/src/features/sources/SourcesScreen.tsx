import { Link } from '@tanstack/react-router';
import { AddSourceForm } from '@/features/sources/AddSourceForm';
import { ChannelCatalogSection } from '@/features/sources/ChannelCatalogSection';
import { SourceListItem } from '@/features/sources/SourceListItem';
import { useHiddenSources } from '@/features/sources/useHiddenSources';
import { useSources } from '@/features/sources/useSources';
import { EmptyState } from '@/shared/ui/EmptyState';
import { Spinner } from '@/shared/ui/Spinner';
import { GridIcon } from '@/shared/ui/icons';

export function SourcesScreen() {
  const { data, status } = useSources();
  const hidden = useHiddenSources();

  if (status === 'pending') {
    return <div className="flex h-full items-center justify-center"><Spinner /></div>;
  }
  if (status === 'error') {
    return <div className="p-6 text-center text-hint">Не удалось загрузить источники.</div>;
  }

  const visibleCount = data.items.length;
  const hiddenCount = hidden.data?.items.length ?? 0;
  const totalCount = visibleCount + hiddenCount;
  return (
    <div>
      <header className="px-4 pb-1 pt-3">
        <h1 className="text-2xl font-bold tracking-tight">Источники</h1>
        <div className="mt-0.5 text-xs text-hint">
          {visibleCount === 0 ? 'пока пусто' : `${visibleCount} ${pluralChannels(visibleCount)}`}
        </div>
      </header>

      <AddSourceForm />

      <section className="mx-3 mt-4">
        <div className="mb-2 flex items-end justify-between">
          <h2 className="text-base font-semibold">Мои источники</h2>
          {hiddenCount > 0 ? (
            <Link
              to="/sources/hidden"
              className="rounded-full bg-secondary px-3 py-1 text-xs text-hint"
            >
              Скрыты из ленты ({hiddenCount})
            </Link>
          ) : null}
        </div>
        {totalCount === 0 ? (
          <EmptyState
            icon={<GridIcon />}
            title="Подключите первый канал"
            body="Введите @username публичного канала — посты появятся в ленте."
          />
        ) : visibleCount > 0 ? (
          <ul className="overflow-hidden rounded-2xl bg-secondary shadow-card">
            {data.items.map((i) => <SourceListItem key={i.channel.id} item={i} />)}
          </ul>
        ) : null}
      </section>

      <ChannelCatalogSection />
    </div>
  );
}

function pluralChannels(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return 'канал';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'канала';
  return 'каналов';
}
