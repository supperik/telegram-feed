import { Avatar } from '@/shared/ui/Avatar';
import { Button } from '@/shared/ui/Button';
import { IconButton } from '@/shared/ui/IconButton';
import { LockIcon, TrashIcon } from '@/shared/ui/icons';
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

const PILL = 'rounded-full bg-secondary px-3 py-1.5 text-[13px] text-hint';

export function CatalogChannelItem(props: Props) {
  const c = props.item.channel;
  return (
    <li className="border-b border-black/10 last:border-b-0">
      <div className="flex items-center gap-3 px-3 py-2.5">
        <Avatar photoUrl={c.photo_url} title={c.title} size={40} />
        <div className="min-w-0 flex-1 leading-tight">
          <div className="truncate text-[14.5px] font-semibold">{c.title}</div>
          <div className="mt-0.5 truncate text-xs text-hint">
            {c.is_private ? (
              <span className="inline-flex items-center gap-1">
                <LockIcon size={12} /> Приватный
              </span>
            ) : c.username ? (
              `@${c.username}`
            ) : (
              '—'
            )}
          </div>
        </div>
        {props.actions === 'available' ? (
          <>
            <SubscribeAction
              item={props.item}
              state={props.subscribeState}
              onSubscribe={props.onSubscribe}
            />
            <IconButton
              aria-label="Скрыть из каталога"
              size={32}
              onClick={() => props.onHide(c.id)}
            >
              <TrashIcon size={16} />
            </IconButton>
          </>
        ) : (
          <Button
            onClick={() => props.onUnhide(c.id)}
            className="rounded-full px-4 py-2 text-[13px] font-semibold"
          >
            ⤴ Вернуть
          </Button>
        )}
      </div>
      {props.actions === 'available' ? (
        <SubscribeStatusLine state={props.subscribeState} />
      ) : null}
    </li>
  );
}

function SubscribeAction({
  item,
  state,
  onSubscribe,
}: {
  item: Item;
  state: SubscribeState;
  onSubscribe: () => void;
}) {
  if (item.is_subscribed || state.kind === 'subscribed') {
    return <span className={PILL}>✓ Подписан</span>;
  }
  if (state.kind === 'submitting' || state.kind === 'queued') {
    return <span className={PILL}>В очереди</span>;
  }
  if (state.kind === 'pending_approval') {
    return <span className={PILL}>Ждёт одобрения</span>;
  }
  return (
    <Button
      onClick={onSubscribe}
      className="rounded-full px-4 py-2 text-[13px] font-semibold"
    >
      + Подписаться
    </Button>
  );
}

function SubscribeStatusLine({ state }: { state: SubscribeState }) {
  if (state.kind === 'queued') {
    return (
      <p className="px-3 pb-2 text-xs text-hint" role="status" aria-live="polite">
        Запрос принят, добавляем…
      </p>
    );
  }
  if (state.kind === 'pending_approval') {
    return (
      <p className="px-3 pb-2 text-xs text-hint" role="status" aria-live="polite">
        Заявка отправлена админу канала. Подписка появится, когда он одобрит.
      </p>
    );
  }
  if (state.kind === 'failed') {
    return (
      <p className="px-3 pb-2 text-xs text-danger" role="alert">
        {state.message}
      </p>
    );
  }
  return null;
}
