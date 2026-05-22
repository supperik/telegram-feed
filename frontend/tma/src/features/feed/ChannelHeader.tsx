import type { ChannelSummary } from '@/shared/api/types';
import { Avatar } from '@/shared/ui/Avatar';
import { LockIcon } from '@/shared/ui/icons';

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
    <header className="tf-cardhead">
      <Avatar photoUrl={channel.photo_url} title={channel.title} size={40} />
      <div className="meta">
        <div className="title">
          {channel.title}
          {channel.is_private ? (
            <span className="lock">
              <LockIcon size={11} />
            </span>
          ) : null}
        </div>
        <div className="sub">
          <span>{channel.username ? `@${channel.username}` : 'приватный'}</span>
          <span className="dot" />
          <span>{formatPostedAt(postedAt)}</span>
        </div>
      </div>
    </header>
  );
}
