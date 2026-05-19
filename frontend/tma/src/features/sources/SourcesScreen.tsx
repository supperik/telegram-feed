import { ChannelCatalogSection } from '@/features/sources/ChannelCatalogSection';
import { AddSourceForm } from '@/features/sources/AddSourceForm';
import { SourceListItem } from '@/features/sources/SourceListItem';
import { useSources } from '@/features/sources/useSources';
import { EmptyState } from '@/shared/ui/EmptyState';
import { Spinner } from '@/shared/ui/Spinner';
import { GridIcon } from '@/shared/ui/icons';

export function SourcesScreen() {
  const { data, status } = useSources();

  if (status === 'pending') {
    return <div className="flex h-full items-center justify-center"><Spinner /></div>;
  }
  if (status === 'error') {
    return <div className="p-6 text-center text-hint">Не удалось загрузить источники.</div>;
  }

  const count = data.items.length;
  return (
    <div>
      <header className="px-4 pb-1 pt-3">
        <h1 className="text-2xl font-bold tracking-tight">Источники</h1>
        <div className="mt-0.5 text-xs text-hint">
          {count === 0 ? 'пока пусто' : `${count} ${pluralChannels(count)}`}
        </div>
      </header>

      <AddSourceForm />

      <ChannelCatalogSection />

      <section className="mx-3 mt-4 mb-20">
        <h2 className="mb-2 text-base font-semibold">Мои источники</h2>
        {count === 0 ? (
          <EmptyState
            icon={<GridIcon />}
            title="Подключите первый канал"
            body="Введите @username публичного канала — посты появятся в ленте."
          />
        ) : (
          <ul className="overflow-hidden rounded-2xl bg-secondary shadow-card">
            {data.items.map((i) => <SourceListItem key={i.channel.id} item={i} />)}
          </ul>
        )}
      </section>
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
