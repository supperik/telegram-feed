import type { ChannelSummary } from '@/shared/api/types';

interface Props {
  channel: ChannelSummary;
  postedAt: string;
}

function formatPostedAt(iso: string): string {
  const d = new Date(iso);
  const diffSec = (Date.now() - d.getTime()) / 1000;
  if (diffSec < 60) return 'just now';
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86_400) return `${Math.floor(diffSec / 3600)}h ago`;
  return d.toLocaleDateString();
}

export function ChannelHeader({ channel, postedAt }: Props) {
  const initial = channel.title[0]?.toUpperCase() ?? '?';
  return (
    <header className="flex items-center gap-3 px-3 pt-3">
      {channel.photo_url ? (
        <img src={channel.photo_url} alt="" className="size-9 rounded-full object-cover" />
      ) : (
        <div className="size-9 rounded-full bg-secondary text-center text-sm leading-9">
          {initial}
        </div>
      )}
      <div className="flex flex-col">
        <span className="text-sm font-medium">{channel.title}</span>
        <span className="text-xs text-hint">
          {channel.username ? `@${channel.username}` : '—'} · {formatPostedAt(postedAt)}
        </span>
      </div>
    </header>
  );
}
