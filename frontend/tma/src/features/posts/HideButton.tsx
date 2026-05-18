import { useHidePost } from '@/features/posts/usePostActions';
import { EyeOffIcon } from '@/shared/ui/icons';

interface Props {
  postId: number;
}

export function HideButton({ postId }: Props) {
  const mut = useHidePost();
  return (
    <button
      type="button"
      aria-label="Hide post"
      onClick={() => mut.mutate(postId)}
      className="inline-flex min-h-9 items-center gap-1.5 rounded-full px-2.5 py-2 text-[13px] text-hint transition active:bg-black/5"
    >
      <EyeOffIcon size={17} />
    </button>
  );
}
