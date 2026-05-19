import { Link } from '@tanstack/react-router';
import { CatalogChannelItem } from '@/features/sources/CatalogChannelItem';
import {
  useChannelCatalog,
  useUnhideFromCatalog,
} from '@/features/sources/useChannelCatalog';
import { Button } from '@/shared/ui/Button';
import { Spinner } from '@/shared/ui/Spinner';
import type { CatalogChannelItem as Item } from '@/shared/api/types';

export function HiddenCatalogScreen() {
  const hidden = useChannelCatalog('hidden');
  const unhide = useUnhideFromCatalog();
  const items: Item[] = hidden.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div>
      <header className="flex items-center gap-2 px-4 pt-3 pb-2">
        <Link to="/sources" className="text-link text-sm">
          ← К источникам
        </Link>
        <h1 className="ml-1 text-base font-semibold">Скрытые из каталога</h1>
      </header>

      {hidden.status === 'pending' ? (
        <div className="flex items-center justify-center py-6"><Spinner /></div>
      ) : items.length === 0 ? (
        <div className="mx-3 rounded-2xl bg-secondary px-4 py-8 text-center text-xs text-hint">
          Нет скрытых каналов.
        </div>
      ) : (
        <ul className="mx-3 overflow-hidden rounded-2xl bg-secondary shadow-card">
          {items.map((it) => (
            <CatalogChannelItem
              key={it.channel.id}
              item={it}
              actions="hidden"
              onUnhide={(id) => unhide.mutate(id)}
            />
          ))}
        </ul>
      )}

      {hidden.hasNextPage ? (
        <div className="mt-2 flex justify-center">
          <Button
            onClick={() => hidden.fetchNextPage()}
            disabled={hidden.isFetchingNextPage}
            className="rounded-full bg-secondary px-4 py-2 text-[13px] text-hint"
          >
            {hidden.isFetchingNextPage ? '…' : 'Показать ещё'}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
