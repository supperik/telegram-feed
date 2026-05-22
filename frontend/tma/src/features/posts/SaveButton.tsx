import { useSavePost } from '@/features/posts/usePostActions';
import { ActionButton } from '@/features/posts/ActionButton';
import { BookmarkFillIcon, BookmarkIcon } from '@/shared/ui/icons';

interface Props {
  postId: number;
  isSaved: boolean;
}

export function SaveButton({ postId, isSaved }: Props) {
  const mut = useSavePost();
  // While the save mutation is in flight, reflect its target state right
  // away — the query cache (and the isSaved prop) lags a beat behind the
  // tap, which made the highlight feel delayed and flicker on rapid re-taps.
  const saved = mut.isPending && mut.variables ? mut.variables.save : isSaved;
  return (
    <ActionButton
      icon={saved ? <BookmarkFillIcon size={16} /> : <BookmarkIcon size={16} />}
      label="Сохранить"
      on={saved}
      aria-label={saved ? 'Unsave post' : 'Save post'}
      aria-pressed={saved}
      onClick={() => mut.mutate({ postId, save: !saved })}
    />
  );
}
