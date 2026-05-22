import { Link } from '@tanstack/react-router';
import { AddSourceForm } from '@/features/sources/AddSourceForm';
import { ChannelCatalogSection } from '@/features/sources/ChannelCatalogSection';
import { SourceListItem } from '@/features/sources/SourceListItem';
import { useHiddenSources } from '@/features/sources/useHiddenSources';
import { useSources } from '@/features/sources/useSources';
import { EmptyState } from '@/shared/ui/EmptyState';
import { PageHeader } from '@/shared/ui/PageHeader';
import { SectionHead } from '@/shared/ui/SectionHead';
import { Spinner } from '@/shared/ui/Spinner';
import { ChevronRightIcon, GridIcon } from '@/shared/ui/icons';

function pluralChannels(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return 'канал';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'канала';
  return 'каналов';
}

export function SourcesScreen() {
  const { data, status } = useSources();
  const hidden = useHiddenSources();

  if (status === 'pending') {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '64px 0' }}>
        <Spinner />
      </div>
    );
  }
  if (status === 'error') {
    return (
      <>
        <PageHeader title="Источники" />
        <p style={{ color: 'var(--hint)', textAlign: 'center', padding: '24px 18px' }}>
          Не удалось загрузить источники.
        </p>
      </>
    );
  }

  const visibleCount = data.items.length;
  const hiddenCount = hidden.data?.items.length ?? 0;
  const totalCount = visibleCount + hiddenCount;

  return (
    <>
      <PageHeader
        title="Источники"
        subtitle={
          visibleCount === 0
            ? 'пока пусто'
            : `${visibleCount} ${pluralChannels(visibleCount)}${
                hiddenCount > 0 ? ` · ${hiddenCount} скрыто` : ''
              }`
        }
      />
      <AddSourceForm />
      <SectionHead
        title="Мои источники"
        action={
          hiddenCount > 0 ? (
            <Link to="/sources/hidden" className="link">
              Скрыты из ленты ({hiddenCount})
              <ChevronRightIcon size={11} />
            </Link>
          ) : undefined
        }
      />
      {totalCount === 0 ? (
        <EmptyState
          icon={<GridIcon size={22} />}
          title="Подключите первый канал"
          body="Введите @username публичного канала — посты появятся в ленте."
        />
      ) : visibleCount > 0 ? (
        <div className="tf-list">
          {data.items.map((i) => (
            <SourceListItem key={i.channel.id} item={i} />
          ))}
        </div>
      ) : null}
      <ChannelCatalogSection />
    </>
  );
}
