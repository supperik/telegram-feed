import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { apiFetch, apiPost } from '@/shared/api/client';
import { SOURCES_QUERY_KEY } from '@/features/sources/useSources';
import type { AddSourceOut, QueueStatusOut } from '@/shared/api/types';

type State =
  | { kind: 'idle' }
  | { kind: 'submitting' }
  | { kind: 'queued'; queueId: number; status: QueueStatusOut['status'] }
  | { kind: 'subscribed' }
  | { kind: 'failed'; message: string };

interface AddSourceResult {
  submit: (username: string) => void;
  state: State;
  reset: () => void;
}

export function useAddSource(): AddSourceResult {
  const qc = useQueryClient();
  const [queueId, setQueueId] = useState<number | null>(null);
  const [state, setState] = useState<State>({ kind: 'idle' });

  const submitMutation = useMutation({
    mutationFn: (username: string) => apiPost<AddSourceOut>('/sources', { username }),
    onMutate: () => setState({ kind: 'submitting' }),
    onSuccess: (data) => {
      if (data.status === 'subscribed') {
        setState({ kind: 'subscribed' });
        qc.invalidateQueries({ queryKey: SOURCES_QUERY_KEY });
      } else {
        setQueueId(data.queue_id);
        setState({ kind: 'queued', queueId: data.queue_id, status: 'pending' });
      }
    },
    onError: (err: Error) => setState({ kind: 'failed', message: err.message }),
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
      } else if (data.status === 'failed') {
        setState({ kind: 'failed', message: data.error_reason ?? 'Channel join failed' });
      } else {
        setState({ kind: 'queued', queueId: queueId!, status: data.status });
      }
      return data;
    },
  });

  return {
    submit: (username) => submitMutation.mutate(username),
    state,
    reset: () => {
      setQueueId(null);
      setState({ kind: 'idle' });
    },
  };
}
