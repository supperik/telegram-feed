import type { MouseEvent } from 'react';

import { ChannelHeader } from '@/features/feed/ChannelHeader';
import { MediaGallery } from '@/features/feed/MediaGallery';
import { PostText } from '@/features/feed/PostText';
import { HideButton } from '@/features/posts/HideButton';
import { SaveButton } from '@/features/posts/SaveButton';
import type { FeedPost } from '@/shared/api/types';
import { openTelegramLink, tgPostUrl } from '@/shared/lib/telegram';
import { EyeIcon, SendIcon, ShareIcon } from '@/shared/ui/icons';

interface Props {
  post: FeedPost;
}

function formatCount(n: number): string {
  if (n < 1000) return String(n);
  if (n < 10_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, '')}k`;
  return `${Math.round(n / 1000)}k`;
}

export function PostCard({ post }: Props) {
  const link = tgPostUrl(post.channel, post.tg_message_id);
  const onOpen = (e: MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    openTelegramLink(link);
  };
  return (
    <article className="mx-3 mb-3 overflow-hidden rounded-2xl bg-secondary shadow-card">
      <ChannelHeader channel={post.channel} postedAt={post.posted_at} />
      <PostText text={post.text} textHtml={post.text_html} />
      <MediaGallery media={post.media} channel={post.channel} tgMessageId={post.tg_message_id} />
      <footer className="flex flex-wrap items-center gap-0.5 px-1.5 pb-2 pt-1">
        {post.views !== null ? (
          <span className="inline-flex min-h-9 items-center gap-1.5 rounded-full px-2.5 py-2 text-[13px] text-hint">
            <EyeIcon size={17} />
            {formatCount(post.views)}
          </span>
        ) : null}
        {post.forwards !== null ? (
          <span className="inline-flex min-h-9 items-center gap-1.5 rounded-full px-2.5 py-2 text-[13px] text-hint">
            <ShareIcon size={17} />
            {formatCount(post.forwards)}
          </span>
        ) : null}
        <SaveButton postId={post.id} isSaved={post.is_saved} />
        <HideButton postId={post.id} />
        <a
          href={link}
          onClick={onOpen}
          aria-label="Open in Telegram"
          className="ml-auto inline-flex h-9 w-9 items-center justify-center rounded-full text-link active:bg-link-soft"
        >
          <SendIcon size={18} />
        </a>
      </footer>
    </article>
  );
}
