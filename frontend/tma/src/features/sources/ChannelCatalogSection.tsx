import { Link } from '@tanstack/react-router';
import { AvailableCatalogRow } from '@/features/sources/AvailableCatalogRow';
import {
  useChannelCatalog,
  useHideFromCatalog,
} from '@/features/sources/useChannelCatalog';
import { Button } from '@/shared/ui/Button';
import { Spinner } from '@/shared/ui/Spinner';
import type { CatalogChannelItem as Item } from '@/shared/api/types';

export function ChannelCatalogSection() {
  const available = useChannelCatalog('available');
  const hidden = useChannelCatalog('hidden');
  const hide = useHideFromCatalog();

  const items: Item[] =
    available.data?.pages.flatMap((p) => p.items) ?? [];
  const hiddenCount = hidden.data?.pages.flatMap((p) => p.items).length ?? 0;
  const hasMore = !!available.hasNextPage;

  return (
    <section className="mx-3 mt-4">
      <div className="mb-2 flex items-end justify-between">
        <h2 className="text-base font-semibold">Доступные каналы</h2>
        {hiddenCount > 0 ? (
          <Link
            to="/sources/catalog-hidden"
            className="rounded-full bg-secondary px-3 py-1 text-xs text-hint"
          >
            Скрытые из каталога: {hiddenCount}
          </Link>
        ) : null}
      </div>

      {available.status === 'pending' ? (
        <div className="flex items-center justify-center py-6">
          <Spinner />
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl bg-secondary px-4 py-6 text-center text-xs text-hint">
          Пока никто не добавил каналов — добавьте свой через форму выше.
        </div>
      ) : (
        <ul className="overflow-hidden rounded-2xl bg-secondary shadow-card">
          {items.map((it) => (
            <AvailableCatalogRow
              key={it.channel.id}
              item={it}
              onHide={(id) => hide.mutate(id)}
            />
          ))}
        </ul>
      )}

      {hasMore ? (
        <div className="mt-2 flex justify-center">
          <Button
            onClick={() => available.fetchNextPage()}
            disabled={available.isFetchingNextPage}
            className="rounded-full bg-secondary px-4 py-2 text-[13px] text-hint"
          >
            {available.isFetchingNextPage ? '…' : 'Показать ещё'}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
