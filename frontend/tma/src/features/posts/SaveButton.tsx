import { useSavePost } from '@/features/posts/usePostActions';
import { ActionButton } from '@/features/posts/ActionButton';
import { BookmarkFillIcon, BookmarkIcon } from '@/shared/ui/icons';

interface Props {
  postId: number;
  isSaved: boolean;
}

export function SaveButton({ postId, isSaved }: Props) {
  const mut = useSavePost();
  return (
    <ActionButton
      icon={isSaved ? <BookmarkFillIcon size={16} /> : <BookmarkIcon size={16} />}
      label="Сохранить"
      on={isSaved}
      aria-label={isSaved ? 'Unsave post' : 'Save post'}
      aria-pressed={isSaved}
      onClick={() => mut.mutate({ postId, save: !isSaved })}
    />
  );
}
