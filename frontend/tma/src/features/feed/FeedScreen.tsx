import { useEffect, useRef } from 'react';
import { useFeed } from '@/features/feed/useFeed';
import { PostCard } from '@/features/feed/PostCard';
import { Button } from '@/shared/ui/Button';
import { Spinner } from '@/shared/ui/Spinner';

export function FeedScreen() {
  const { data, status, error, hasNextPage, isFetchingNextPage, fetchNextPage, refetch, isFetching } = useFeed();
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || !hasNextPage) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting) && !isFetchingNextPage) fetchNextPage();
      },
      { rootMargin: '200px' },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  if (status === 'pending') {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );
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
      <div className="flex items-center justify-end px-3 py-2">
        <Button variant="ghost" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? 'Refreshing…' : 'Refresh'}
        </Button>
      </div>
      {posts.length === 0 ? (
        <div className="p-6 text-center text-hint">
          No posts yet. Add channels in the Sources tab.
        </div>
      ) : null}
      {posts.map((p) => <PostCard key={p.id} post={p} />)}
      <div ref={sentinelRef} className="flex h-12 items-center justify-center">
        {isFetchingNextPage ? <Spinner /> : hasNextPage ? <span className="text-xs text-hint">Loading more…</span> : null}
      </div>
    </div>
  );
}
