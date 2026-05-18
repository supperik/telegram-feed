import { useSavePost } from '@/features/posts/usePostActions';
import { BookmarkIcon } from '@/shared/ui/icons';

interface Props {
  postId: number;
  isSaved: boolean;
}

export function SaveButton({ postId, isSaved }: Props) {
  const mut = useSavePost();
  const next = !isSaved;
  return (
    <button
      type="button"
      aria-label={isSaved ? 'Unsave post' : 'Save post'}
      aria-pressed={isSaved}
      onClick={() => mut.mutate({ postId, save: next })}
      className={`inline-flex min-h-9 items-center gap-1.5 rounded-full px-2.5 py-2 text-[13px] transition active:bg-black/5 ${
        isSaved ? 'text-link [&_svg]:fill-link' : 'text-hint'
      }`}
    >
      <BookmarkIcon size={17} />
    </button>
  );
}
