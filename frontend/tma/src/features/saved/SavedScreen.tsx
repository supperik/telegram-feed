import { useEffect, useRef, useState } from 'react';
import type { InfiniteData, UseInfiniteQueryResult } from '@tanstack/react-query';
import { PostCard, type PostCardActions } from '@/features/feed/PostCard';
import { useHiddenPosts } from '@/features/posts/useHiddenPosts';
import { useReadPosts } from '@/features/posts/useReadPosts';
import { useSavedPosts } from '@/features/posts/useSavedPosts';
import type { FeedPage } from '@/shared/api/types';
import { Button } from '@/shared/ui/Button';
import { EmptyState } from '@/shared/ui/EmptyState';
import { Spinner } from '@/shared/ui/Spinner';
import { BookmarkIcon, EyeIcon, EyeOffIcon } from '@/shared/ui/icons';

type Tab = 'saved' | 'hidden' | 'read';

export function SavedScreen() {
  const [tab, setTab] = useState<Tab>('saved');
  const saved = useSavedPosts();
  const hidden = useHiddenPosts();
  const read = useReadPosts();

  return (
    <div>
      <header className="px-4 pb-2 pt-3">
        <h1 className="text-2xl font-bold tracking-tight">Сохранёнки</h1>
        <div className="mt-2 flex gap-1 rounded-full bg-secondary p-1">
          <TabButton active={tab === 'saved'} onClick={() => setTab('saved')}>
            Сохранённые
          </TabButton>
          <TabButton active={tab === 'hidden'} onClick={() => setTab('hidden')}>
            Скрытые
          </TabButton>
          <TabButton active={tab === 'read'} onClick={() => setTab('read')}>
            Просмотренные
          </TabButton>
        </div>
      </header>

      {tab === 'saved' ? (
        <PostList
          query={saved}
          actions="saved"
          emptyIcon={<BookmarkIcon />}
          emptyTitle="Здесь будут сохранённые посты"
          emptyBody="Нажмите 🔖 в карточке поста, чтобы вернуться к нему позже."
        />
      ) : tab === 'hidden' ? (
        <PostList
          query={hidden}
          actions="hidden"
          emptyIcon={<EyeOffIcon />}
          emptyTitle="Скрытых постов нет"
          emptyBody="Когда вы скроете пост из ленты, он появится здесь — отсюда же можно его вернуть."
        />
      ) : (
        <PostList
          query={read}
          actions="feed"
          emptyIcon={<EyeIcon />}
          emptyTitle="Просмотренных постов пока нет"
          emptyBody="Посты, которые вы пролистали в ленте, собираются здесь — лента их больше не показывает."
        />
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`flex-1 rounded-full px-3 py-1.5 text-sm font-medium transition ${
        active ? 'bg-button text-button-text shadow-sm' : 'text-hint'
      }`}
    >
      {children}
    </button>
  );
}

type PostListQuery = UseInfiniteQueryResult<InfiniteData<FeedPage, unknown>, Error>;

interface PostListProps {
  query: PostListQuery;
  actions: PostCardActions;
  emptyIcon: React.ReactNode;
  emptyTitle: string;
  emptyBody: string;
}

function PostList({ query, actions, emptyIcon, emptyTitle, emptyBody }: PostListProps) {
  const { data, status, error, hasNextPage, isFetchingNextPage, fetchNextPage, refetch } = query;
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
      <div className="flex h-40 items-center justify-center">
        <Spinner />
      </div>
    );
  }
  if (status === 'error') {
    return (
      <div className="flex h-40 flex-col items-center justify-center gap-3 p-6">
        <p className="text-hint">{(error as Error).message}</p>
        <Button onClick={() => refetch()}>Retry</Button>
      </div>
    );
  }

  const posts = data.pages.flatMap((p) => p.posts);
  if (posts.length === 0) {
    return <EmptyState icon={emptyIcon} title={emptyTitle} body={emptyBody} />;
  }

  return (
    <>
      {posts.map((p) => (
        <PostCard key={p.id} post={p} actions={actions} />
      ))}
      <div ref={sentinelRef} className="flex h-12 items-center justify-center">
        {isFetchingNextPage ? (
          <Spinner />
        ) : hasNextPage ? (
          <span className="text-xs text-hint">Загружаем ещё…</span>
        ) : null}
      </div>
    </>
  );
}
