import { useMutation, useQueryClient, type InfiniteData } from '@tanstack/react-query';
import { apiFetch } from '@/shared/api/client';
import { FEED_QUERY_KEY } from '@/features/feed/useFeed';
import { HIDDEN_POSTS_QUERY_KEY } from '@/features/posts/useHiddenPosts';
import { SAVED_POSTS_QUERY_KEY } from '@/features/posts/useSavedPosts';
import { CATALOG_QUERY_KEY } from '@/features/sources/useChannelCatalog';
import { HIDDEN_SOURCES_QUERY_KEY } from '@/features/sources/useHiddenSources';
import { SOURCES_QUERY_KEY } from '@/features/sources/useSources';
import type {
  FeedPage,
  HiddenSourceList,
  SourceList,
  SourceListItem,
} from '@/shared/api/types';

type FeedCache = InfiniteData<FeedPage, unknown>;
type QueryClient = ReturnType<typeof useQueryClient>;
type PageSnap = Array<[unknown, FeedCache | undefined]>;

function snapshotAndPatch(
  qc: QueryClient,
  queryKey: readonly unknown[],
  patch: (page: FeedPage) => FeedPage,
): PageSnap {
  const all = qc.getQueriesData<FeedCache>({ queryKey });
  for (const [key, data] of all) {
    if (!data) continue;
    qc.setQueryData<FeedCache>(key, {
      ...data,
      pages: data.pages.map(patch),
    });
  }
  return all;
}

function rollback(qc: QueryClient, snap: PageSnap): void {
  for (const [key, prev] of snap) {
    qc.setQueryData(key as readonly unknown[], prev);
  }
}

export function useSavePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ postId, save }: { postId: number; save: boolean }) =>
      apiFetch<void>(`/posts/${postId}/save`, { method: save ? 'POST' : 'DELETE' }),
    onMutate: async ({ postId, save }) => {
      await qc.cancelQueries({ queryKey: FEED_QUERY_KEY });
      await qc.cancelQueries({ queryKey: SAVED_POSTS_QUERY_KEY });
      await qc.cancelQueries({ queryKey: HIDDEN_POSTS_QUERY_KEY });
      const feedSnap = snapshotAndPatch(qc, FEED_QUERY_KEY, (page) => ({
        ...page,
        posts: page.posts.map((p) => (p.id === postId ? { ...p, is_saved: save } : p)),
      }));
      const hiddenSnap = snapshotAndPatch(qc, HIDDEN_POSTS_QUERY_KEY, (page) => ({
        ...page,
        posts: page.posts.map((p) => (p.id === postId ? { ...p, is_saved: save } : p)),
      }));
      // Don't yank the row out of the saved list on unsave — a mistaken
      // tap shouldn't visually delete the card. The bookmark icon flips to
      // empty so the user sees what happened; the row disappears only on
      // the next refetch.
      const savedSnap = snapshotAndPatch(qc, SAVED_POSTS_QUERY_KEY, (page) => ({
        ...page,
        posts: page.posts.map((p) => (p.id === postId ? { ...p, is_saved: save } : p)),
      }));
      return { feedSnap, hiddenSnap, savedSnap };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.feedSnap) rollback(qc, ctx.feedSnap);
      if (ctx?.hiddenSnap) rollback(qc, ctx.hiddenSnap);
      if (ctx?.savedSnap) rollback(qc, ctx.savedSnap);
    },
    onSettled: (_d, _e, { save }) => {
      // After a save we need the server-side saved list (with the new row
      // and its saved_at timestamp) to be the truth.
      if (save) qc.invalidateQueries({ queryKey: SAVED_POSTS_QUERY_KEY });
    },
  });
}

export function useHidePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (postId: number) =>
      apiFetch<void>(`/posts/${postId}/hide`, { method: 'POST' }),
    onMutate: async (postId) => {
      await qc.cancelQueries({ queryKey: FEED_QUERY_KEY });
      const feedSnap = snapshotAndPatch(qc, FEED_QUERY_KEY, (page) => ({
        ...page,
        posts: page.posts.filter((p) => p.id !== postId),
      }));
      return { feedSnap };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.feedSnap) rollback(qc, ctx.feedSnap);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: HIDDEN_POSTS_QUERY_KEY });
    },
  });
}

export function useUnhidePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (postId: number) =>
      apiFetch<void>(`/posts/${postId}/hide`, { method: 'DELETE' }),
    // No optimistic patch of the hidden list — a mistaken tap shouldn't
    // visually delete the card. The row leaves the list only on the next
    // refetch of the tab.
    onSettled: () => {
      // Returning the post to the feed depends on its posted_at relative to
      // whatever cursor pages we already have — let the server resolve it.
      qc.invalidateQueries({ queryKey: FEED_QUERY_KEY });
    },
  });
}

export function useHideSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (item: SourceListItem) =>
      apiFetch<void>(`/sources/${item.channel.id}/hide`, { method: 'POST' }),
    onMutate: async (item) => {
      const channelId = item.channel.id;
      await qc.cancelQueries({ queryKey: FEED_QUERY_KEY });
      await qc.cancelQueries({ queryKey: SOURCES_QUERY_KEY });
      await qc.cancelQueries({ queryKey: HIDDEN_SOURCES_QUERY_KEY });
      const feedSnap = snapshotAndPatch(qc, FEED_QUERY_KEY, (page) => ({
        ...page,
        posts: page.posts.filter((p) => p.channel.id !== channelId),
      }));
      const prevSources = qc.getQueryData<SourceList>(SOURCES_QUERY_KEY);
      qc.setQueryData<SourceList>(SOURCES_QUERY_KEY, (old) =>
        old ? { items: old.items.filter((s) => s.channel.id !== channelId) } : old,
      );
      const prevHidden = qc.getQueryData<HiddenSourceList>(HIDDEN_SOURCES_QUERY_KEY);
      qc.setQueryData<HiddenSourceList>(HIDDEN_SOURCES_QUERY_KEY, (old) => {
        const next = { channel: item.channel, hidden_at: new Date().toISOString() };
        if (!old) return { items: [next] };
        if (old.items.some((h) => h.channel.id === channelId)) return old;
        return { items: [next, ...old.items] };
      });
      return { feedSnap, prevSources, prevHidden };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.feedSnap) rollback(qc, ctx.feedSnap);
      if (ctx?.prevSources) qc.setQueryData(SOURCES_QUERY_KEY, ctx.prevSources);
      if (ctx?.prevHidden) qc.setQueryData(HIDDEN_SOURCES_QUERY_KEY, ctx.prevHidden);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: SOURCES_QUERY_KEY });
      qc.invalidateQueries({ queryKey: HIDDEN_SOURCES_QUERY_KEY });
      qc.invalidateQueries({ queryKey: CATALOG_QUERY_KEY });
    },
  });
}
