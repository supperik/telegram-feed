import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { InfiniteData, UseInfiniteQueryResult } from '@tanstack/react-query';
import { PostCard, type PostCardActions } from '@/features/feed/PostCard';
import { useHiddenPosts } from '@/features/posts/useHiddenPosts';
import { useReadPosts } from '@/features/posts/useReadPosts';
import { useSavedPosts } from '@/features/posts/useSavedPosts';
import type { FeedPage } from '@/shared/api/types';
import { EmptyState } from '@/shared/ui/EmptyState';
import { PillTabs } from '@/shared/ui/PillTabs';
import { Spinner } from '@/shared/ui/Spinner';
import { AlertCircleIcon, BookmarkIcon, EyeIcon, EyeOffIcon } from '@/shared/ui/icons';

type Tab = 'saved' | 'hidden' | 'read';

const TABS = [
  { id: 'saved', label: 'Сохранённые' },
  { id: 'hidden', label: 'Скрытые' },
  { id: 'read', label: 'Просмотренные' },
];

export function SavedScreen() {
  const [tab, setTab] = useState<Tab>('saved');
  const saved = useSavedPosts();
  const hidden = useHiddenPosts();
  const read = useReadPosts();

  return (
    <>
      <header
        className="tf-pageheader"
        style={{ flexDirection: 'column', alignItems: 'stretch', gap: 14, paddingBottom: 14 }}
      >
        <h1>Сохранёнки</h1>
        <PillTabs tabs={TABS} active={tab} onChange={(id) => setTab(id as Tab)} />
      </header>

      {tab === 'saved' ? (
        <PostList
          query={saved}
          actions="saved"
          emptyIcon={<BookmarkIcon size={22} />}
          emptyTitle="Здесь будут сохранённые посты"
          emptyBody="Нажмите «Сохранить» в карточке поста, чтобы вернуться к нему позже."
        />
      ) : tab === 'hidden' ? (
        <PostList
          query={hidden}
          actions="hidden"
          emptyIcon={<EyeOffIcon size={22} />}
          emptyTitle="Скрытых постов нет"
          emptyBody="Когда вы скроете пост из ленты, он появится здесь — отсюда же можно его вернуть."
        />
      ) : (
        <PostList
          query={read}
          actions="feed"
          emptyIcon={<EyeIcon size={22} />}
          emptyTitle="Просмотренных постов пока нет"
          emptyBody="Посты, которые вы пролистали в ленте, собираются здесь — лента их больше не показывает."
        />
      )}
    </>
  );
}

type PostListQuery = UseInfiniteQueryResult<InfiniteData<FeedPage, unknown>, Error>;

interface PostListProps {
  query: PostListQuery;
  actions: PostCardActions;
  emptyIcon: ReactNode;
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
      <div style={{ display: 'flex', justifyContent: 'center', padding: '48px 0' }}>
        <Spinner />
      </div>
    );
  }
  if (status === 'error') {
    return (
      <EmptyState
        icon={<AlertCircleIcon size={24} />}
        title="Не удалось загрузить"
        body={(error as Error).message}
        actionLabel="Повторить"
        onAction={() => refetch()}
      />
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
      <div
        ref={sentinelRef}
        style={{ display: 'flex', minHeight: 48, alignItems: 'center', justifyContent: 'center' }}
      >
        {isFetchingNextPage ? <Spinner /> : null}
      </div>
    </>
  );
}
