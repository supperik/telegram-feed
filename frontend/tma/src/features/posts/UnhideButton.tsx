import { useUnhidePost } from '@/features/posts/usePostActions';
import { EyeIcon } from '@/shared/ui/icons';

interface Props {
  postId: number;
}

export function UnhideButton({ postId }: Props) {
  const mut = useUnhidePost();
  return (
    <button
      type="button"
      aria-label="Unhide post"
      onClick={() => mut.mutate(postId)}
      className="inline-flex min-h-9 items-center gap-1.5 rounded-full px-2.5 py-2 text-[13px] text-hint transition active:bg-black/5"
    >
      <EyeIcon size={17} />
      <span>Вернуть</span>
    </button>
  );
}
