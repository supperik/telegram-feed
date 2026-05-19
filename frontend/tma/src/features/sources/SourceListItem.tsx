import { useHideSource } from '@/features/posts/usePostActions';
import { useRemoveSource } from '@/features/sources/useSources';
import { Avatar } from '@/shared/ui/Avatar';
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog';
import { IconButton } from '@/shared/ui/IconButton';
import { EyeOffIcon, LockIcon, TrashIcon } from '@/shared/ui/icons';
import type { SourceListItem as Item } from '@/shared/api/types';

interface Props {
  item: Item;
}

export function SourceListItem({ item }: Props) {
  const remove = useRemoveSource();
  const hide = useHideSource();
  const c = item.channel;
  const pending = item.subscription_status === 'pending_backfill';

  const onDelete = () => {
    const title = c.title || (c.username ? `@${c.username}` : 'канал');
    if (ConfirmDialog.confirm(`Удалить канал «${title}» из подписок?`)) {
      remove.mutate(c.id);
    }
  };

  return (
    <li className="flex items-center gap-3 border-b border-black/10 px-3 py-2.5 last:border-b-0">
      <Avatar photoUrl={c.photo_url} title={c.title} size={40} />
      <div className="min-w-0 flex-1 leading-tight">
        <div className="truncate text-[14.5px] font-semibold">{c.title}</div>
        <div className={`mt-0.5 truncate text-xs ${pending ? 'text-[#b45309]' : 'text-hint'}`}>
          {c.is_private ? (
            <span className="inline-flex items-center gap-1">
              <LockIcon size={12} /> Приватный
            </span>
          ) : c.username ? (
            `@${c.username}`
          ) : (
            '—'
          )}
          {pending ? ' · подгружаем…' : null}
        </div>
      </div>
      <IconButton aria-label="Скрыть" size={32} onClick={() => hide.mutate(item)}>
        <EyeOffIcon size={16} />
      </IconButton>
      <IconButton aria-label="Удалить" size={32} variant="danger" onClick={onDelete}>
        <TrashIcon size={16} />
      </IconButton>
    </li>
  );
}
