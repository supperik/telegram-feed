import { useUnhideSource } from '@/features/sources/useHiddenSources';
import { useRemoveSource } from '@/features/sources/useSources';
import { Avatar } from '@/shared/ui/Avatar';
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog';
import { EyeIcon, LockIcon, TrashIcon } from '@/shared/ui/icons';
import type { HiddenSourceItem as Item } from '@/shared/api/types';

interface Props {
  item: Item;
}

const LOCK_STYLE = { display: 'inline-flex', color: 'var(--hint)' } as const;

export function HiddenSourceListItem({ item }: Props) {
  const unhide = useUnhideSource();
  const remove = useRemoveSource();
  const c = item.channel;

  const onDelete = async () => {
    const title = c.title || (c.username ? `@${c.username}` : 'канал');
    if (await ConfirmDialog.confirm(`Удалить канал «${title}» из подписок?`)) {
      remove.mutate(c.id);
    }
  };

  return (
    <div className="tf-row">
      <Avatar photoUrl={c.photo_url} title={c.title} size={40} />
      <div className="meta">
        <div className="title">
          {c.title}
          {c.is_private ? (
            <span style={LOCK_STYLE}>
              <LockIcon size={11} />
            </span>
          ) : null}
        </div>
        <div className="sub">
          <span>{c.is_private ? 'Приватный' : c.username ? `@${c.username}` : '—'}</span>
        </div>
      </div>
      <div className="controls">
        <button
          type="button"
          className="iconbtn"
          aria-label="Вернуть в ленту"
          onClick={() => unhide.mutate(item)}
        >
          <EyeIcon size={15} />
        </button>
        <button
          type="button"
          className="iconbtn"
          data-variant="danger"
          aria-label="Удалить"
          onClick={onDelete}
        >
          <TrashIcon size={15} />
        </button>
      </div>
    </div>
  );
}
