import { Avatar } from '@/shared/ui/Avatar';
import { Button } from '@/shared/ui/Button';
import { IconButton } from '@/shared/ui/IconButton';
import { LockIcon, TrashIcon } from '@/shared/ui/icons';
import type { CatalogChannelItem as Item } from '@/shared/api/types';

interface AvailableProps {
  item: Item;
  actions: 'available';
  onSubscribe: (channelId: number) => void;
  onHide: (channelId: number) => void;
}

interface HiddenProps {
  item: Item;
  actions: 'hidden';
  onUnhide: (channelId: number) => void;
}

type Props = AvailableProps | HiddenProps;

export function CatalogChannelItem(props: Props) {
  const c = props.item.channel;
  return (
    <li className="flex items-center gap-3 border-b border-black/10 px-3 py-2.5 last:border-b-0">
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
          {props.item.is_subscribed ? (
            <span className="rounded-full bg-secondary px-3 py-1.5 text-[13px] text-hint">
              ✓ Подписан
            </span>
          ) : (
            <Button
              onClick={() => props.onSubscribe(c.id)}
              className="rounded-full px-4 py-2 text-[13px] font-semibold"
            >
              + Подписаться
            </Button>
          )}
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
    </li>
  );
}
