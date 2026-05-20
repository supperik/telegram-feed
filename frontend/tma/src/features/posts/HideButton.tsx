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
      className="inline-flex flex-col items-center gap-1 rounded-xl px-2.5 py-1.5 text-[11px] text-hint transition active:bg-black/5"
    >
      <EyeOffIcon size={17} />
      <span>Скрыть</span>
    </button>
  );
}
