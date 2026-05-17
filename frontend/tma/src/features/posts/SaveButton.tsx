import { useSavePost } from '@/features/posts/usePostActions';

interface Props {
  postId: number;
  isSaved: boolean;
}

export function SaveButton({ postId, isSaved }: Props) {
  const mut = useSavePost();
  const next = !isSaved;
  return (
    <button
      aria-label={isSaved ? 'Unsave post' : 'Save post'}
      onClick={() => mut.mutate({ postId, save: next })}
      className={`px-2 py-1 text-sm ${isSaved ? 'text-link' : 'text-hint'}`}
    >
      {isSaved ? '★ Saved' : '☆ Save'}
    </button>
  );
}
