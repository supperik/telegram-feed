import { Avatar } from '@/shared/ui/Avatar';
import {
  CheckIcon,
  ClockIcon,
  EyeIcon,
  EyeOffIcon,
  LoaderIcon,
  LockIcon,
  PlusIcon,
  UsersIcon,
} from '@/shared/ui/icons';
import type { SubscribeState } from '@/features/sources/useChannelCatalog';
import type { CatalogChannelItem as Item } from '@/shared/api/types';

interface AvailableProps {
  item: Item;
  actions: 'available';
  subscribeState: SubscribeState;
  onSubscribe: () => void;
  onHide: (channelId: number) => void;
}

interface HiddenProps {
  item: Item;
  actions: 'hidden';
  onUnhide: (channelId: number) => void;
}

type Props = AvailableProps | HiddenProps;

function fmtNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace('.0', '')}M`;
  if (n >= 1000) return `${Math.round(n / 1000)}K`;
  return String(n);
}

function fmtLastPost(iso: string): string {
  const sec = (Date.now() - new Date(iso).getTime()) / 1000;
  if (sec < 3600) return `${Math.max(1, Math.floor(sec / 60))} мин`;
  if (sec < 86_400) return `${Math.floor(sec / 3600)} ч`;
  if (sec < 7 * 86_400) return `${Math.floor(sec / 86_400)} дн`;
  return new Date(iso).toLocaleDateString();
}

const HANDLE_PRIVATE = { display: 'inline-flex', alignItems: 'center', gap: 4 } as const;

export function CatalogChannelItem(props: Props) {
  const c = props.item.channel;
  const hue = ((c.username ?? c.title ?? '?').charCodeAt(0) * 23) % 360;
  return (
    <div className="tf-cattile">
      <div
        className="banner"
        style={{
          background: `linear-gradient(135deg, oklch(0.45 0.1 ${hue}), oklch(0.28 0.06 ${(hue + 60) % 360}))`,
        }}
      >
        <div className="av-frame">
          <Avatar photoUrl={c.photo_url} title={c.title} size={38} />
        </div>
      </div>
      <div className="body">
        <div className="name">{c.title}</div>
        <div className="handle">
          {c.is_private ? (
            <span style={HANDLE_PRIVATE}>
              <LockIcon size={10} /> Приватный
            </span>
          ) : c.username ? (
            `@${c.username}`
          ) : (
            '—'
          )}
        </div>
        <div className="stats">
          <UsersIcon size={11} />
          <span>{fmtNum(props.item.subscribers_count)}</span>
          {props.item.last_post_at ? (
            <>
              <span className="pip" />
              <ClockIcon size={11} />
              <span>{fmtLastPost(props.item.last_post_at)}</span>
            </>
          ) : null}
        </div>
      </div>
      {props.actions === 'available' ? (
        <AvailableCta
          item={props.item}
          state={props.subscribeState}
          onSubscribe={props.onSubscribe}
          onHide={() => props.onHide(c.id)}
        />
      ) : (
        <div className="cta">
          <button
            type="button"
            className="sub-btn"
            data-state="subscribed"
            onClick={() => props.onUnhide(c.id)}
          >
            <EyeIcon size={13} /> Вернуть в каталог
          </button>
        </div>
      )}
    </div>
  );
}

function AvailableCta({
  item,
  state,
  onSubscribe,
  onHide,
}: {
  item: Item;
  state: SubscribeState;
  onSubscribe: () => void;
  onHide: () => void;
}) {
  const subscribed = item.is_subscribed || state.kind === 'subscribed';
  const queued = state.kind === 'submitting' || state.kind === 'queued';
  const pending = state.kind === 'pending_approval';

  let btn;
  if (subscribed) {
    btn = (
      <button type="button" className="sub-btn" data-state="subscribed" disabled>
        <CheckIcon size={13} /> Подписан
      </button>
    );
  } else if (queued) {
    btn = (
      <button type="button" className="sub-btn" data-state="queued" disabled>
        <LoaderIcon className="tf-spin" size={13} /> В очереди
      </button>
    );
  } else if (pending) {
    btn = (
      <button type="button" className="sub-btn" data-state="pending" disabled>
        <ClockIcon size={13} /> Ждёт одобрения
      </button>
    );
  } else {
    btn = (
      <button type="button" className="sub-btn" onClick={onSubscribe}>
        <PlusIcon size={14} /> Подписаться
      </button>
    );
  }

  return (
    <>
      <div className="cta">
        {btn}
        <button
          type="button"
          className="hide-btn"
          aria-label="Скрыть из каталога"
          onClick={onHide}
        >
          <EyeOffIcon size={14} />
        </button>
      </div>
      {state.kind === 'queued' ? (
        <p className="tf-cattile-msg" role="status" aria-live="polite">
          Запрос принят, добавляем…
        </p>
      ) : null}
      {state.kind === 'pending_approval' ? (
        <p className="tf-cattile-msg" role="status" aria-live="polite">
          Заявка отправлена админу канала. Подписка появится, когда он одобрит.
        </p>
      ) : null}
      {state.kind === 'failed' ? (
        <p className="tf-cattile-msg is-danger" role="alert">
          {state.message}
        </p>
      ) : null}
    </>
  );
}
