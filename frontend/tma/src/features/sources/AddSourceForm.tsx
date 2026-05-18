import { useState } from 'react';
import { useAddSource } from '@/features/sources/useAddSource';

/**
 * Loose client-side sanity check only — actual parsing (username vs invite link)
 * happens server-side via the dispatcher in backend/src/services/sources/.
 * Accepts: @username, bare usernames, https://t.me/<name>, https://t.me/+<hash>.
 */
const SANITY_RE = /^[\sA-Za-z0-9@_+\-/:.]+$/;
const MAX_LEN = 256;

export function AddSourceForm() {
  const [value, setValue] = useState('');
  const { submit, state, reset } = useAddSource();

  const handle = () => {
    const cleaned = value.trim();
    if (cleaned.length === 0 || cleaned.length > MAX_LEN) return;
    if (!SANITY_RE.test(cleaned)) return;
    submit(cleaned);
  };

  const disabled =
    state.kind === 'submitting' || state.kind === 'queued' || state.kind === 'pending_approval';

  return (
    <div className="mx-3 mt-3 rounded-2xl bg-secondary p-3 shadow-card">
      <div className="flex items-center gap-2">
        <span className="flex h-7 w-7 select-none items-center justify-center text-base font-semibold text-hint">@</span>
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="@username или https://t.me/+..."
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
          {state.kind === 'submitting' ? '…' : 'Подписаться'}
        </button>
      </div>
      <div className="mt-1 px-1 text-xs text-hint">Публичные и приватные каналы</div>
      <div className="mt-2 px-1 text-xs">
        {state.kind === 'queued' ? (
          <span className="text-hint" role="status" aria-live="polite">
            Запрос принят, добавляем…
          </span>
        ) : null}
        {state.kind === 'pending_approval' ? (
          <span className="text-hint" role="status" aria-live="polite">
            Заявка отправлена админу канала. Подписка появится в списке, как только админ одобрит.
          </span>
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
          <span className="text-danger" role="alert">{state.message}</span>
        ) : null}
      </div>
    </div>
  );
}
