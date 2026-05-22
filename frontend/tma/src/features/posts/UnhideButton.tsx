import { useState } from 'react';
import { useHidePost, useUnhidePost } from '@/features/posts/usePostActions';
import { ActionButton } from '@/features/posts/ActionButton';
import { EyeIcon, EyeOffIcon } from '@/shared/ui/icons';

interface Props {
  postId: number;
}

export function UnhideButton({ postId }: Props) {
  // On the hidden tab posts start as hidden; the button toggles state so a
  // mistaken tap can be undone right there without leaving the tab.
  const [hidden, setHidden] = useState(true);
  const hideMut = useHidePost();
  const unhideMut = useUnhidePost();
  const onClick = () => {
    if (hidden) {
      unhideMut.mutate(postId);
      setHidden(false);
    } else {
      hideMut.mutate(postId);
      setHidden(true);
    }
  };
  return (
    <ActionButton
      icon={hidden ? <EyeOffIcon size={16} /> : <EyeIcon size={16} />}
      label={hidden ? 'Скрыт' : 'В ленте'}
      on={!hidden}
      aria-label={hidden ? 'Unhide post' : 'Hide post'}
      aria-pressed={!hidden}
      onClick={onClick}
    />
  );
}
