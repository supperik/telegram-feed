import { useState } from 'react';
import { useAddSource } from '@/features/sources/useAddSource';
import { Button } from '@/shared/ui/Button';

const USERNAME_RE = /^[A-Za-z0-9_]+$/;

export function AddSourceForm() {
  const [value, setValue] = useState('');
  const { submit, state, reset } = useAddSource();

  const handle = () => {
    const cleaned = value.trim().replace(/^@/, '');
    if (!USERNAME_RE.test(cleaned)) return;
    submit(cleaned);
  };

  return (
    <div className="border-b border-hint/10 p-3">
      <div className="flex gap-2">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="username (e.g. meduzaproject)"
          className="flex-1 rounded bg-secondary px-3 py-2 text-sm"
          autoCapitalize="off"
          autoCorrect="off"
        />
        <Button onClick={handle} disabled={state.kind === 'submitting' || state.kind === 'queued'}>
          {state.kind === 'submitting' ? '…' : 'Add'}
        </Button>
      </div>
      <div className="mt-2 text-xs">
        {state.kind === 'queued' ? (
          <span className="text-hint">Queued ({state.status})…</span>
        ) : null}
        {state.kind === 'subscribed' ? (
          <button
            className="text-link"
            onClick={() => {
              setValue('');
              reset();
            }}
          >
            Subscribed — add another
          </button>
        ) : null}
        {state.kind === 'failed' ? (
          <span className="text-red-500">{state.message}</span>
        ) : null}
      </div>
    </div>
  );
}
