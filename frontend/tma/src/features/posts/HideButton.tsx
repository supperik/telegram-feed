import { useHidePost } from '@/features/posts/usePostActions';
import { ActionButton } from '@/features/posts/ActionButton';
import { EyeOffIcon } from '@/shared/ui/icons';

interface Props {
  postId: number;
}

export function HideButton({ postId }: Props) {
  const mut = useHidePost();
  return (
    <ActionButton
      icon={<EyeOffIcon size={16} />}
      label="Скрыть"
      aria-label="Hide post"
      onClick={() => mut.mutate(postId)}
    />
  );
}
