import { useHidePost } from '@/features/posts/usePostActions';

interface Props {
  postId: number;
}

export function HideButton({ postId }: Props) {
  const mut = useHidePost();
  return (
    <button
      aria-label="Hide post"
      onClick={() => mut.mutate(postId)}
      className="px-2 py-1 text-sm text-hint"
    >
      ✕ Hide
    </button>
  );
}
