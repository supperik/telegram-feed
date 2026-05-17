import { useHideSource } from '@/features/posts/usePostActions';
import { useRemoveSource } from '@/features/sources/useSources';
import { Button } from '@/shared/ui/Button';
import type { SourceListItem as Item } from '@/shared/api/types';

interface Props {
  item: Item;
}

export function SourceListItem({ item }: Props) {
  const remove = useRemoveSource();
  const hide = useHideSource();
  const c = item.channel;
  const initial = c.title[0]?.toUpperCase() ?? '?';
  return (
    <li className="flex items-center gap-3 border-b border-hint/10 px-3 py-2">
      {c.photo_url ? (
        <img src={c.photo_url} alt="" className="size-9 rounded-full object-cover" />
      ) : (
        <div className="size-9 rounded-full bg-secondary text-center text-sm leading-9">
          {initial}
        </div>
      )}
      <div className="flex flex-1 flex-col">
        <span className="text-sm font-medium">{c.title}</span>
        <span className="text-xs text-hint">
          {c.username ? `@${c.username}` : '—'}
          {item.subscription_status === 'pending_backfill' ? ' · backfilling…' : null}
        </span>
      </div>
      <Button variant="ghost" onClick={() => hide.mutate(c.id)}>
        Hide
      </Button>
      <Button variant="secondary" onClick={() => remove.mutate(c.id)}>
        Remove
      </Button>
    </li>
  );
}
