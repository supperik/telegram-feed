import type { MouseEvent } from 'react';

import { ChannelHeader } from '@/features/feed/ChannelHeader';
import { MediaGallery } from '@/features/feed/MediaGallery';
import { PostText } from '@/features/feed/PostText';
import type { PostReadTracker } from '@/features/feed/usePostRead';
import { HideButton } from '@/features/posts/HideButton';
import { SaveButton } from '@/features/posts/SaveButton';
import { UnhideButton } from '@/features/posts/UnhideButton';
import type { FeedPost } from '@/shared/api/types';
import { openTelegramLink, tgPostUrl } from '@/shared/lib/telegram';
import { ArrowUpRightIcon } from '@/shared/ui/icons';

export type PostCardActions = 'feed' | 'saved' | 'hidden';

interface Props {
  post: FeedPost;
  actions?: PostCardActions;
  readTracker?: PostReadTracker;
}

export function PostCard({ post, actions = 'feed', readTracker }: Props) {
  // For private channels with an invite link, the Telegram button leads to
  // the invite (a non-member can join; an already-member is taken to the
  // channel). For everything else it deep-links to the post itself.
  const link = post.channel.invite_url ?? tgPostUrl(post.channel, post.tg_message_id);
  const onOpen = (e: MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    readTracker?.markRead(post.id);
    openTelegramLink(link);
  };
  return (
    <article ref={readTracker?.observe(post.id)} className="tf-card">
      <ChannelHeader channel={post.channel} postedAt={post.posted_at} />
      <PostText text={post.text} textHtml={post.text_html} />
      <MediaGallery media={post.media} channel={post.channel} tgMessageId={post.tg_message_id} />
      <footer className="tf-cardfoot">
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
          className="tf-action"
          data-variant="open"
        >
          <ArrowUpRightIcon size={16} />
        </a>
      </footer>
    </article>
  );
}
