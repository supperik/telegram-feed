import { useEffect, useRef, useState, type MouseEvent } from 'react';
import { ChevronDownIcon } from '@/shared/ui/icons';

interface Props {
  text: string | null;
  textHtml: string | null;
}

// Past this rendered-text length the body is clamped to a few lines behind a
// fade, with a read-more toggle (and tap-to-expand on the text itself).
const CLAMP_THRESHOLD = 320;

export function PostText({ text, textHtml }: Props) {
  const [open, setOpen] = useState(false);
  const [needsClamp, setNeedsClamp] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setNeedsClamp((el.textContent ?? '').length > CLAMP_THRESHOLD);
  }, [text, textHtml]);

  if (!textHtml && !text) return null;

  const clamped = needsClamp && !open;
  const className = `tf-cardtext${clamped ? ' is-clamped is-tappable' : ''}`;

  const handleClick = (e: MouseEvent<HTMLDivElement>) => {
    const spoiler = (e.target as HTMLElement).closest('.tg-spoiler');
    if (spoiler) {
      spoiler.classList.add('is-revealed');
      return;
    }
    // Let real links through; only the collapsed body expands on tap.
    if ((e.target as HTMLElement).closest('a')) return;
    if (clamped) setOpen(true);
  };

  const shared = {
    ref,
    className,
    onClick: handleClick,
    role: clamped ? ('button' as const) : undefined,
    'aria-expanded': needsClamp ? open : undefined,
  };

  return (
    <>
      {textHtml ? (
        <div {...shared} dangerouslySetInnerHTML={{ __html: textHtml }} />
      ) : (
        <div {...shared}>{text}</div>
      )}
      {needsClamp ? (
        <button type="button" className="tf-readmore" onClick={() => setOpen((v) => !v)}>
          {open ? 'Свернуть' : 'Раскрыть текст'}
          <span style={{ display: 'inline-flex', transform: open ? 'rotate(180deg)' : 'none' }}>
            <ChevronDownIcon size={13} />
          </span>
        </button>
      ) : null}
    </>
  );
}
