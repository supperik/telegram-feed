import type { MouseEvent } from 'react';

import { ChannelHeader } from '@/features/feed/ChannelHeader';
import { MediaGallery } from '@/features/feed/MediaGallery';
import { PostText } from '@/features/feed/PostText';
import { HideButton } from '@/features/posts/HideButton';
import { SaveButton } from '@/features/posts/SaveButton';
import { UnhideButton } from '@/features/posts/UnhideButton';
import type { FeedPost } from '@/shared/api/types';
import { openTelegramLink, tgPostUrl } from '@/shared/lib/telegram';
import { SendIcon } from '@/shared/ui/icons';

export type PostCardActions = 'feed' | 'saved' | 'hidden';

interface Props {
  post: FeedPost;
  actions?: PostCardActions;
}

export function PostCard({ post, actions = 'feed' }: Props) {
  // For private channels with an invite link, the Telegram button leads to
  // the invite (a non-member can join; an already-member is taken to the
  // channel). For everything else it deep-links to the post itself.
  const link = post.channel.invite_url ?? tgPostUrl(post.channel, post.tg_message_id);
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
        <SaveButton postId={post.id} isSaved={post.is_saved} />
        {actions === 'hidden' ? (
          <UnhideButton postId={post.id} />
        ) : (
          <HideButton postId={post.id} />
        )}
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
