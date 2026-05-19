import { useMutation, useQueryClient, type InfiniteData } from '@tanstack/react-query';
import { apiFetch } from '@/shared/api/client';
import { FEED_QUERY_KEY } from '@/features/feed/useFeed';
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

function snapshotAndPatchFeed(
  qc: ReturnType<typeof useQueryClient>,
  patch: (page: FeedPage) => FeedPage,
): Array<[unknown, FeedCache | undefined]> {
  const all = qc.getQueriesData<FeedCache>({ queryKey: FEED_QUERY_KEY });
  for (const [key, data] of all) {
    if (!data) continue;
    qc.setQueryData<FeedCache>(key, {
      ...data,
      pages: data.pages.map(patch),
    });
  }
  return all;
}

function rollbackFeed(
  qc: ReturnType<typeof useQueryClient>,
  snap: Array<[unknown, FeedCache | undefined]>,
): void {
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
      const snap = snapshotAndPatchFeed(qc, (page) => ({
        ...page,
        posts: page.posts.map((p) => (p.id === postId ? { ...p, is_saved: save } : p)),
      }));
      return { snap };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.snap) rollbackFeed(qc, ctx.snap);
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
      const snap = snapshotAndPatchFeed(qc, (page) => ({
        ...page,
        posts: page.posts.filter((p) => p.id !== postId),
      }));
      return { snap };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.snap) rollbackFeed(qc, ctx.snap);
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
      const feedSnap = snapshotAndPatchFeed(qc, (page) => ({
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
      if (ctx?.feedSnap) rollbackFeed(qc, ctx.feedSnap);
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
