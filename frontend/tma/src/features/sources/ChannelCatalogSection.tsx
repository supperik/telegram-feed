import { Link } from '@tanstack/react-router';
import { useState } from 'react';
import { AvailableCatalogRow } from '@/features/sources/AvailableCatalogRow';
import {
  useChannelCatalog,
  useChannelCategories,
  useHideFromCatalog,
} from '@/features/sources/useChannelCatalog';
import { Button } from '@/shared/ui/Button';
import { SectionHead } from '@/shared/ui/SectionHead';
import { Spinner } from '@/shared/ui/Spinner';
import { ChevronRightIcon } from '@/shared/ui/icons';
import { useDebouncedValue } from '@/shared/hooks/useDebouncedValue';
import type { CatalogChannelItem as Item } from '@/shared/api/types';

const NOTE_STYLE = {
  color: 'var(--hint)',
  font: '500 13px/1.5 var(--font-ui)',
  textAlign: 'center',
  padding: '8px 18px 20px',
} as const;

const SEARCH_STYLE = {
  display: 'block',
  width: 'calc(100% - 24px)',
  margin: '6px 12px 12px',
  padding: '12px 14px',
  background: 'var(--surface)',
  color: 'var(--text)',
  border: '1.5px solid var(--border-soft)',
  borderRadius: 'var(--r-full)',
  font: '500 14px/1 var(--font-ui)',
  outline: 'none',
} as const;

const TABS_STYLE = {
  display: 'flex',
  gap: 8,
  overflowX: 'auto',
  padding: '0 12px 12px',
  scrollbarWidth: 'none',
} as const;

const TAB_STYLE = {
  flex: '0 0 auto',
  padding: '8px 14px',
  borderRadius: 'var(--r-full)',
  border: '1.5px solid var(--border-soft)',
  background: 'var(--surface)',
  color: 'var(--text-mid)',
  font: '600 13px/1 var(--font-ui)',
  cursor: 'pointer',
} as const;

const TAB_ACTIVE_STYLE = {
  ...TAB_STYLE,
  background: 'var(--accent)',
  color: 'var(--accent-on)',
  border: '1.5px solid var(--accent)',
} as const;

export function ChannelCatalogSection() {
  const [query, setQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const debouncedQuery = useDebouncedValue(query.trim(), 250);
  const available = useChannelCatalog(
    'available',
    debouncedQuery || undefined,
    activeCategory ?? undefined,
  );
  const hidden = useChannelCatalog('hidden');
  const categories = useChannelCategories();
  const hide = useHideFromCatalog();

  const items: Item[] = available.data?.pages.flatMap((p) => p.items) ?? [];
  const hiddenCount = hidden.data?.pages.flatMap((p) => p.items).length ?? 0;
  const hasQuery = debouncedQuery.length > 0;

  return (
    <section>
      <SectionHead
        title="Доступные каналы"
        action={
          hiddenCount > 0 ? (
            <Link to="/sources/catalog-hidden" className="link">
              Скрытые: {hiddenCount}
              <ChevronRightIcon size={11} />
            </Link>
          ) : undefined
        }
      />
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Поиск по каталогу"
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
        style={SEARCH_STYLE}
      />
      <div style={TABS_STYLE} role="tablist" aria-label="Категории каналов">
        <button
          type="button"
          role="tab"
          aria-selected={activeCategory === null}
          style={activeCategory === null ? TAB_ACTIVE_STYLE : TAB_STYLE}
          onClick={() => setActiveCategory(null)}
        >
          Все
        </button>
        {(categories.data ?? []).map((cat) => {
          const isActive = activeCategory === cat.slug;
          return (
            <button
              key={cat.slug}
              type="button"
              role="tab"
              aria-selected={isActive}
              style={isActive ? TAB_ACTIVE_STYLE : TAB_STYLE}
              onClick={() => setActiveCategory(isActive ? null : cat.slug)}
            >
              {cat.title}
            </button>
          );
        })}
      </div>
      {available.status === 'pending' ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '24px 0' }}>
          <Spinner />
        </div>
      ) : items.length === 0 ? (
        <p style={NOTE_STYLE}>
          {hasQuery || activeCategory
            ? 'Ничего не найдено по запросу'
            : 'Пока никто не добавил каналов — добавьте свой через форму выше.'}
        </p>
      ) : (
        <div className="tf-catgrid">
          {items.map((it) => (
            <AvailableCatalogRow key={it.channel.id} item={it} onHide={(id) => hide.mutate(id)} />
          ))}
        </div>
      )}
      {available.hasNextPage ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '16px 0' }}>
          <Button
            variant="secondary"
            onClick={() => available.fetchNextPage()}
            disabled={available.isFetchingNextPage}
          >
            {available.isFetchingNextPage ? '…' : 'Показать ещё'}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
