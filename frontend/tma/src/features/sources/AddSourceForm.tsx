import { useState } from 'react';
import { useAddSource } from '@/features/sources/useAddSource';

const USERNAME_RE = /^[A-Za-z0-9_]+$/;

export function AddSourceForm() {
  const [value, setValue] = useState('');
  const { submit, state, reset } = useAddSource();

  const handle = () => {
    const cleaned = value.trim().replace(/^@/, '');
    if (!USERNAME_RE.test(cleaned)) return;
    submit(cleaned);
  };

  const disabled = state.kind === 'submitting' || state.kind === 'queued';

  return (
    <div className="mx-3 mt-3 rounded-2xl bg-secondary p-3 shadow-card">
      <div className="flex items-center gap-2">
        <span className="flex h-7 w-7 select-none items-center justify-center text-base font-semibold text-hint">@</span>
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="username канала (например, meduzaproject)"
          className="flex-1 bg-transparent text-[15px] outline-none placeholder:text-hint"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
        />
        <button
          type="button"
          onClick={handle}
          disabled={disabled}
          className="rounded-full bg-button px-4 py-2 text-[13px] font-semibold text-button-text transition active:opacity-90 disabled:opacity-45"
        >
          {state.kind === 'submitting' ? '…' : 'Добавить'}
        </button>
      </div>
      <div className="mt-2 px-1 text-xs">
        {state.kind === 'queued' ? (
          <span className="text-hint">Подгружаем посты ({state.status})…</span>
        ) : null}
        {state.kind === 'subscribed' ? (
          <button
            type="button"
            className="text-link"
            onClick={() => { setValue(''); reset(); }}
          >
            Готово — добавить ещё канал
          </button>
        ) : null}
        {state.kind === 'failed' ? (
          <span className="text-danger">{state.message}</span>
        ) : null}
      </div>
    </div>
  );
}
