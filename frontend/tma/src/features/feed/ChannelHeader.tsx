import type { ChannelSummary } from '@/shared/api/types';
import { Avatar } from '@/shared/ui/Avatar';

interface Props {
  channel: ChannelSummary;
  postedAt: string;
}

function formatPostedAt(iso: string): string {
  const d = new Date(iso);
  const diffSec = (Date.now() - d.getTime()) / 1000;
  if (diffSec < 60) return 'только что';
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} мин`;
  if (diffSec < 86_400) return `${Math.floor(diffSec / 3600)} ч`;
  return d.toLocaleDateString();
}

export function ChannelHeader({ channel, postedAt }: Props) {
  return (
    <header className="flex items-center gap-3 px-3.5 pt-3 pb-1.5">
      <Avatar photoUrl={channel.photo_url} title={channel.title} size={44} />
      <div className="min-w-0 flex-1 leading-tight">
        <div className="truncate text-[15px] font-semibold">{channel.title}</div>
        <div className="mt-0.5 text-xs text-hint">
          {channel.username ? `@${channel.username}` : '—'} · {formatPostedAt(postedAt)}
        </div>
      </div>
    </header>
  );
}
