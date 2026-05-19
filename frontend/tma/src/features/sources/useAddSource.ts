import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { apiFetch, apiPost } from '@/shared/api/client';
import { HIDDEN_SOURCES_QUERY_KEY } from '@/features/sources/useHiddenSources';
import { SOURCES_QUERY_KEY } from '@/features/sources/useSources';
import type { AddSourceIn, AddSourceOut, QueueStatusOut } from '@/shared/api/types';

/**
 * Maps backend error_code values to Russian user-facing copy. Canonical
 * codes are emitted in backend/src/ingester/join_worker.py and
 * backend/src/ingester/approval_poller.py. `unknown` is the catch-all when
 * the backend returns a code we don't yet localize.
 */
export const ERROR_MESSAGES: Record<string, string> = {
  invite_invalid: 'Неверная ссылка',
  invite_expired: 'Ссылка истекла',
  channels_too_much: 'Превышен лимит каналов у бота',
  flood_wait: 'Слишком много запросов, попробуй позже',
  approval_timeout: 'Админ не одобрил заявку за 7 дней',
  username_not_occupied: 'Канал с таким username не найден',
  username_invalid: 'Неверный username',
  channel_private: 'Канал недоступен этому боту',
  channel_not_found: 'Канал не найден',
  channel_not_available: 'Канал временно недоступен',
  channel_banned: 'Канал заблокирован',
  unknown: 'Не удалось добавить',
};

type State =
  | { kind: 'idle' }
  | { kind: 'submitting' }
  | { kind: 'queued'; queueId: number; status: QueueStatusOut['status'] }
  | { kind: 'pending_approval'; queueId: number }
  | { kind: 'subscribed' }
  | { kind: 'failed'; message: string; errorCode: string | null };

interface AddSourceResult {
  submit: (input: string) => void;
  state: State;
  reset: () => void;
}

const FALLBACK_MESSAGE = ERROR_MESSAGES.unknown ?? 'Не удалось добавить';

function messageFor(errorCode: string | null | undefined): string {
  if (errorCode) {
    const localized = ERROR_MESSAGES[errorCode];
    if (localized) return localized;
  }
  return FALLBACK_MESSAGE;
}

export function useAddSource(): AddSourceResult {
  const qc = useQueryClient();
  const [queueId, setQueueId] = useState<number | null>(null);
  const [state, setState] = useState<State>({ kind: 'idle' });

  const submitMutation = useMutation({
    mutationFn: (input: string) => apiPost<AddSourceOut>('/sources', { input } satisfies AddSourceIn),
    onMutate: () => setState({ kind: 'submitting' }),
    onSuccess: (data) => {
      if (data.status === 'subscribed') {
        setState({ kind: 'subscribed' });
        qc.invalidateQueries({ queryKey: SOURCES_QUERY_KEY });
        qc.invalidateQueries({ queryKey: HIDDEN_SOURCES_QUERY_KEY });
      } else {
        setQueueId(data.queue_id);
        setState({ kind: 'queued', queueId: data.queue_id, status: 'pending' });
      }
    },
    onError: (err: Error) => {
      // Network or 4xx/5xx — surface the API error message; no error_code yet.
      setState({ kind: 'failed', message: err.message || FALLBACK_MESSAGE, errorCode: null });
    },
  });

  useQuery<QueueStatusOut>({
    queryKey: ['queue', queueId],
    enabled: queueId !== null,
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d) return 2000;
      return d.status === 'pending' || d.status === 'in_progress' ? 2000 : false;
    },
    queryFn: async () => {
      const data = await apiFetch<QueueStatusOut>(`/sources/queue/${queueId}`);
      if (data.status === 'done') {
        setState({ kind: 'subscribed' });
        qc.invalidateQueries({ queryKey: SOURCES_QUERY_KEY });
      } else if (data.status === 'pending_approval') {
        setState({ kind: 'pending_approval', queueId: queueId! });
      } else if (data.status === 'failed') {
        setState({
          kind: 'failed',
          message: messageFor(data.error_code),
          errorCode: data.error_code,
        });
      } else {
        setState({ kind: 'queued', queueId: queueId!, status: data.status });
      }
      return data;
    },
  });

  return {
    submit: (input) => submitMutation.mutate(input),
    state,
    reset: () => {
      setQueueId(null);
      setState({ kind: 'idle' });
    },
  };
}
