import { useState } from 'react';
import { useAddSource } from '@/features/sources/useAddSource';
import { AlertCircleIcon, CheckIcon, ClockIcon, LoaderIcon, PlusIcon } from '@/shared/ui/icons';

/**
 * Loose client-side sanity check only — actual parsing (username vs invite link)
 * happens server-side via the dispatcher in backend/src/services/sources/.
 * Accepts: @username, bare usernames, https://t.me/<name>, https://t.me/+<hash>.
 */
const SANITY_RE = /^[\sA-Za-z0-9@_+\-/:.]+$/;
const MAX_LEN = 256;

const HINT_STYLE = { display: 'inline-flex', alignItems: 'center', gap: 4 } as const;
const RESET_BTN = {
  ...HINT_STYLE,
  cursor: 'pointer',
  background: 'none',
  border: 0,
  padding: 0,
  font: 'inherit',
  color: 'inherit',
} as const;

export function AddSourceForm() {
  const [value, setValue] = useState('');
  const { submit, state, reset } = useAddSource();

  const handle = () => {
    const cleaned = value.trim();
    if (cleaned.length === 0 || cleaned.length > MAX_LEN) return;
    if (!SANITY_RE.test(cleaned)) return;
    submit(cleaned);
  };

  const busy =
    state.kind === 'submitting' || state.kind === 'queued' || state.kind === 'pending_approval';

  return (
    <>
      <div className="tf-addcard">
        <PlusIcon size={16} />
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="@username или t.me/+..."
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
        />
        <button type="button" onClick={handle} disabled={busy}>
          {state.kind === 'submitting' ? '…' : 'Подписаться'}
        </button>
      </div>
      <div
        className={
          'tf-addhint' +
          (state.kind === 'pending_approval' ? ' is-warn' : '') +
          (state.kind === 'subscribed' ? ' is-success' : '') +
          (state.kind === 'failed' ? ' is-danger' : '')
        }
      >
        {state.kind === 'idle' || state.kind === 'submitting' ? (
          <span>Публичные и приватные каналы</span>
        ) : null}
        {state.kind === 'queued' ? (
          <span role="status" aria-live="polite" style={HINT_STYLE}>
            <LoaderIcon className="tf-spin" size={12} />
            Запрос принят, добавляем…
          </span>
        ) : null}
        {state.kind === 'pending_approval' ? (
          <span role="status" aria-live="polite" style={HINT_STYLE}>
            <ClockIcon size={12} />
            Заявка отправлена админу канала. Подписка появится в списке, как только админ одобрит.
          </span>
        ) : null}
        {state.kind === 'subscribed' ? (
          <button type="button" style={RESET_BTN} onClick={() => { setValue(''); reset(); }}>
            <CheckIcon size={12} />
            Готово — добавить ещё канал
          </button>
        ) : null}
        {state.kind === 'failed' ? (
          <span role="alert" style={HINT_STYLE}>
            <AlertCircleIcon size={12} />
            {state.message}
          </span>
        ) : null}
      </div>
    </>
  );
}
