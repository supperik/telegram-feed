import { useEffect, useRef } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useFeed } from '@/features/feed/useFeed';
import { PostCard } from '@/features/feed/PostCard';
import { Button } from '@/shared/ui/Button';
import { EmptyState } from '@/shared/ui/EmptyState';
import { IconButton } from '@/shared/ui/IconButton';
import { Spinner } from '@/shared/ui/Spinner';
import { AlertCircleIcon, RefreshIcon } from '@/shared/ui/icons';

export function FeedScreen() {
  const navigate = useNavigate();
  const {
    data, status, error, hasNextPage, isFetchingNextPage, fetchNextPage, refetch, isFetching,
  } = useFeed();
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
    return <div className="flex h-full items-center justify-center"><Spinner /></div>;
  }
  if (status === 'error') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6">
        <p className="text-hint">{(error as Error).message}</p>
        <Button onClick={() => refetch()}>Retry</Button>
      </div>
    );
  }

  const posts = data.pages.flatMap((p) => p.posts);

  return (
    <div>
      <header className="flex items-end justify-between px-4 pb-1 pt-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Лента</h1>
          {isFetching ? (
            <div className="mt-0.5 text-xs text-hint">обновляем…</div>
          ) : null}
        </div>
        <IconButton
          aria-label="Refresh feed"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <RefreshIcon size={18} />
        </IconButton>
      </header>

      {posts.length === 0 ? (
        <EmptyState
          icon={<AlertCircleIcon />}
          title="Лента пока пуста"
          body="Добавьте Telegram-каналы — посты будут собираться сюда автоматически."
          actionLabel="Добавить каналы →"
          onAction={() => navigate({ to: '/sources' })}
        />
      ) : null}

      {posts.map((p) => <PostCard key={p.id} post={p} />)}

      <div ref={sentinelRef} className="flex h-12 items-center justify-center">
        {isFetchingNextPage ? <Spinner /> : hasNextPage ? <span className="text-xs text-hint">Загружаем ещё…</span> : null}
      </div>
    </div>
  );
}
