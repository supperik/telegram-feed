import { ChannelHeader } from '@/features/feed/ChannelHeader';
import { MediaGallery } from '@/features/feed/MediaGallery';
import { HideButton } from '@/features/posts/HideButton';
import { SaveButton } from '@/features/posts/SaveButton';
import type { FeedPost } from '@/shared/api/types';

interface Props {
  post: FeedPost;
}

function tgPostUrl(post: FeedPost): string | null {
  if (!post.channel.username) return null;
  return `tg://resolve?domain=${post.channel.username}&post=${post.tg_message_id}`;
}

export function PostCard({ post }: Props) {
  const link = tgPostUrl(post);
  return (
    <article className="mb-2 border-b border-hint/10 bg-bg pb-3">
      <ChannelHeader channel={post.channel} postedAt={post.posted_at} />
      {post.text ? (
        <div className="whitespace-pre-wrap break-words px-3 py-2 text-sm">{post.text}</div>
      ) : null}
      <MediaGallery media={post.media} channel={post.channel} tgMessageId={post.tg_message_id} />
      <footer className="mt-2 flex items-center justify-between px-3 text-xs text-hint">
        <span>
          {post.views !== null ? `${post.views} views` : null}
          {post.forwards !== null ? ` · ${post.forwards} forwards` : null}
        </span>
        <div className="flex items-center gap-2">
          <SaveButton postId={post.id} isSaved={post.is_saved} />
          <HideButton postId={post.id} />
          {link ? (
            <a href={link} className="text-link" aria-label="Open in Telegram">Open</a>
          ) : null}
        </div>
      </footer>
    </article>
  );
}
