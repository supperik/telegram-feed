import { useState } from 'react';
import { useHidePost, useUnhidePost } from '@/features/posts/usePostActions';
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
    <button
      type="button"
      aria-label={hidden ? 'Unhide post' : 'Hide post'}
      aria-pressed={!hidden}
      onClick={onClick}
      className={`inline-flex min-h-9 items-center gap-1.5 rounded-full px-2.5 py-2 text-[13px] transition active:bg-black/5 ${
        hidden ? 'text-hint' : 'text-link'
      }`}
    >
      {hidden ? <EyeOffIcon size={17} /> : <EyeIcon size={17} />}
      <span>{hidden ? 'Скрыт' : 'В ленте'}</span>
    </button>
  );
}
