import { Link } from '@tanstack/react-router';
import { CatalogChannelItem } from '@/features/sources/CatalogChannelItem';
import { useChannelCatalog, useUnhideFromCatalog } from '@/features/sources/useChannelCatalog';
import { Button } from '@/shared/ui/Button';
import { SubHeader } from '@/shared/ui/SubHeader';
import { Spinner } from '@/shared/ui/Spinner';
import { ChevronLeftIcon } from '@/shared/ui/icons';
import type { CatalogChannelItem as Item } from '@/shared/api/types';

export function HiddenCatalogScreen() {
  const hidden = useChannelCatalog('hidden');
  const unhide = useUnhideFromCatalog();
  const items: Item[] = hidden.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <>
      <SubHeader
        title="Скрытые из каталога"
        back={
          <Link to="/sources" className="back" aria-label="К источникам">
            <ChevronLeftIcon size={16} />
          </Link>
        }
      />
      {hidden.status === 'pending' ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
          <Spinner />
        </div>
      ) : items.length === 0 ? (
        <p
          style={{
            color: 'var(--hint)',
            font: '500 13px/1.5 var(--font-ui)',
            textAlign: 'center',
            padding: '24px 18px',
          }}
        >
          Нет скрытых каналов.
        </p>
      ) : (
        <div className="tf-catgrid" style={{ marginTop: 8 }}>
          {items.map((it) => (
            <CatalogChannelItem
              key={it.channel.id}
              item={it}
              actions="hidden"
              onUnhide={(id) => unhide.mutate(id)}
            />
          ))}
        </div>
      )}
      {hidden.hasNextPage ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '16px 0' }}>
          <Button
            variant="secondary"
            onClick={() => hidden.fetchNextPage()}
            disabled={hidden.isFetchingNextPage}
          >
            {hidden.isFetchingNextPage ? '…' : 'Показать ещё'}
          </Button>
        </div>
      ) : null}
    </>
  );
}
