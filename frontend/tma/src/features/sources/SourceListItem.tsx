import { useHideSource } from '@/features/posts/usePostActions';
import { useRemoveSource } from '@/features/sources/useSources';
import { Avatar } from '@/shared/ui/Avatar';
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog';
import { EyeOffIcon, LoaderIcon, LockIcon, TrashIcon } from '@/shared/ui/icons';
import type { SourceListItem as Item } from '@/shared/api/types';

interface Props {
  item: Item;
}

const LOCK_STYLE = { display: 'inline-flex', color: 'var(--hint)' } as const;

export function SourceListItem({ item }: Props) {
  const remove = useRemoveSource();
  const hide = useHideSource();
  const c = item.channel;
  const pending = item.subscription_status === 'pending_backfill';

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
        <div className={`sub${pending ? ' is-warn' : ''}`}>
          <span>{c.is_private ? 'Приватный' : c.username ? `@${c.username}` : '—'}</span>
          {pending ? (
            <>
              <span className="dot" />
              <LoaderIcon className="tf-spin" size={11} />
              <span>подгружаем…</span>
            </>
          ) : null}
        </div>
      </div>
      <div className="controls">
        <button
          type="button"
          className="iconbtn"
          aria-label="Скрыть из ленты"
          onClick={() => hide.mutate(item)}
        >
          <EyeOffIcon size={15} />
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
