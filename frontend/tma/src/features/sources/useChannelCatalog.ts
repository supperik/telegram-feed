import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { useState } from 'react';
import { apiFetch } from '@/shared/api/client';
import { ApiError } from '@/shared/api/errors';
import { messageFor } from '@/features/sources/useAddSource';
import { SOURCES_QUERY_KEY } from '@/features/sources/useSources';
import type {
  AddSourceOut,
  CatalogPage,
  ChannelCategoriesResponse,
  ChannelCategory,
  QueueStatusOut,
} from '@/shared/api/types';

export const CATALOG_QUERY_KEY = ['catalog'] as const;

type View = 'available' | 'hidden';

/** Per-channel state of a catalog row's «Подписаться» button. */
export type SubscribeState =
  | { kind: 'idle' }
  | { kind: 'submitting' }
  | { kind: 'queued' }
  | { kind: 'pending_approval' }
  | { kind: 'subscribed' }
  | { kind: 'failed'; message: string };

export function useChannelCatalog(view: View, q?: string, category?: string) {
  return useInfiniteQuery<CatalogPage>({
    queryKey: [...CATALOG_QUERY_KEY, view, q ?? '', category ?? ''],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const search = new URLSearchParams({ view });
      if (q) search.set('q', q);
      if (category) search.set('category', category);
      if (pageParam) search.set('cursor', pageParam as string);
      return apiFetch<CatalogPage>(`/channels/catalog?${search.toString()}`);
    },
    getNextPageParam: (last) => last.next_cursor,
  });
}

export const CHANNEL_CATEGORIES_QUERY_KEY = ['channel-categories'] as const;

export function useChannelCategories() {
  return useQuery<ChannelCategory[]>({
    queryKey: CHANNEL_CATEGORIES_QUERY_KEY,
    queryFn: async () => {
      const r = await apiFetch<ChannelCategoriesResponse>('/channels/categories');
      return r.categories;
    },
    staleTime: 60 * 60 * 1000,
  });
}

/**
 * Subscribe to one catalog channel. A dormant/left channel reactivates through
 * the join queue — the backend answers POST /sources/{id} with 202 queued — so,
 * like useAddSource, this polls /sources/queue/{id} until the join settles
 * instead of assuming the subscription took effect right away.
 */
export function useSubscribeByChannelId(channelId: number) {
  const qc = useQueryClient();
  const [queueId, setQueueId] = useState<number | null>(null);
  const [state, setState] = useState<SubscribeState>({ kind: 'idle' });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: SOURCES_QUERY_KEY });
    qc.invalidateQueries({ queryKey: CATALOG_QUERY_KEY });
  };

  const submitMutation = useMutation({
    mutationFn: () =>
      apiFetch<AddSourceOut>(`/sources/${channelId}`, { method: 'POST' }),
    onMutate: () => setState({ kind: 'submitting' }),
    onSuccess: (data) => {
      if (data.status === 'subscribed') {
        setState({ kind: 'subscribed' });
        invalidate();
      } else {
        setQueueId(data.queue_id);
        setState({ kind: 'queued' });
      }
    },
    onError: (err: Error) => {
      const code = err instanceof ApiError ? err.code : null;
      setState({ kind: 'failed', message: messageFor(code) });
    },
  });

  useQuery<QueueStatusOut>({
    queryKey: ['queue', queueId],
    enabled: queueId !== null,
    refetchInterval: (query) => {
      const d = query.state.data;
      if (!d) return 2000;
      return d.status === 'pending' || d.status === 'in_progress' ? 2000 : false;
    },
    queryFn: async () => {
      const data = await apiFetch<QueueStatusOut>(`/sources/queue/${queueId}`);
      if (data.status === 'done') {
        setState({ kind: 'subscribed' });
        invalidate();
      } else if (data.status === 'pending_approval') {
        setState({ kind: 'pending_approval' });
      } else if (data.status === 'failed') {
        setState({ kind: 'failed', message: messageFor(data.error_code) });
      } else {
        // Poll re-runs every 2s while the join is pending — keep the same state
        // reference so unchanged ticks don't re-render the row.
        setState((s) => (s.kind === 'queued' ? s : { kind: 'queued' }));
      }
      return data;
    },
  });

  return { subscribe: () => submitMutation.mutate(), state };
}

export function useHideFromCatalog() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (channelId: number) =>
      apiFetch<void>(`/channels/catalog/${channelId}/hide`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: CATALOG_QUERY_KEY }),
  });
}

export function useUnhideFromCatalog() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (channelId: number) =>
      apiFetch<void>(`/channels/catalog/${channelId}/hide`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: CATALOG_QUERY_KEY }),
  });
}
