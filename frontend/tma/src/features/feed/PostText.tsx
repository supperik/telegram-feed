import type { MouseEvent } from 'react';

interface Props {
  text: string | null;
  textHtml: string | null;
}

const CONTAINER_CLASS =
  'post-text whitespace-pre-wrap break-words px-3.5 pb-2 pt-1 text-[14.5px] leading-relaxed';

function handleClick(e: MouseEvent<HTMLDivElement>) {
  const target = (e.target as HTMLElement).closest('.tg-spoiler');
  if (target) {
    target.classList.add('is-revealed');
  }
}

export function PostText({ text, textHtml }: Props) {
  if (textHtml) {
    return (
      <div
        className={CONTAINER_CLASS}
        onClick={handleClick}
        dangerouslySetInnerHTML={{ __html: textHtml }}
      />
    );
  }
  if (text) {
    return <div className={CONTAINER_CLASS}>{text}</div>;
  }
  return null;
}
