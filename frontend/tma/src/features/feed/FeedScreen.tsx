import { useEffect, useRef } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useFeed } from '@/features/feed/useFeed';
import { usePostRead } from '@/features/feed/usePostRead';
import { PostCard } from '@/features/feed/PostCard';
import { EmptyState } from '@/shared/ui/EmptyState';
import { PageHeader } from '@/shared/ui/PageHeader';
import { Spinner } from '@/shared/ui/Spinner';
import { AlertCircleIcon } from '@/shared/ui/icons';

export function FeedScreen() {
  const navigate = useNavigate();
  const {
    data, status, error, hasNextPage, isFetchingNextPage, fetchNextPage, refetch, isFetching,
  } = useFeed();
  const readTracker = usePostRead();
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || !hasNextPage) return;
    const obs = new IntersectionObserver(
      (entries) => { if (entries.some((e) => e.isIntersecting) && !isFetchingNextPage) fetchNextPage(); },
      { rootMargin: '200px' },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

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
        <PageHeader title="Лента" />
        <EmptyState
          icon={<AlertCircleIcon size={24} />}
          title="Не удалось загрузить ленту"
          body={(error as Error).message}
          actionLabel="Повторить"
          onAction={() => refetch()}
        />
      </>
    );
  }

  const posts = data.pages.flatMap((p) => p.posts);

  return (
    <>
      <PageHeader
        title="Лента"
        subtitle={isFetching ? 'обновляем…' : undefined}
        onRefresh={() => refetch()}
        refreshing={isFetching}
      />
      {posts.length === 0 ? (
        <EmptyState
          icon={<AlertCircleIcon size={24} />}
          title="Лента пока пуста"
          body="Добавьте Telegram-каналы — посты будут собираться сюда автоматически."
          actionLabel="Добавить каналы"
          onAction={() => navigate({ to: '/sources' })}
        />
      ) : (
        posts.map((p) => <PostCard key={p.id} post={p} readTracker={readTracker} />)
      )}
      <div
        ref={sentinelRef}
        style={{ display: 'flex', minHeight: 48, alignItems: 'center', justifyContent: 'center' }}
      >
        {isFetchingNextPage ? <Spinner /> : null}
      </div>
    </>
  );
}
