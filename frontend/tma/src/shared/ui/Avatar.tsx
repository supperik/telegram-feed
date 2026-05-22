import type { CSSProperties } from 'react';
import { getTokens } from '@/features/auth/tokenStore';

interface Props {
  photoUrl: string | null;
  title: string;
  size?: number;
}

function authedImageUrl(url: string | null): string | null {
  if (!url) return null;
  if (/^https?:/.test(url)) return url;
  const tokens = getTokens();
  if (!tokens) return url;
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}token=${encodeURIComponent(tokens.access_token)}`;
}

export function Avatar({ photoUrl, title, size = 40 }: Props) {
  const base: CSSProperties = {
    width: size,
    height: size,
    fontSize: Math.round(size * 0.42),
    borderRadius: '9999px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
    flexShrink: 0,
    fontWeight: 700,
    lineHeight: 1,
    letterSpacing: '-0.01em',
  };
  const resolved = authedImageUrl(photoUrl);
  if (resolved) {
    return (
      <div className="avatar" style={base}>
        <img src={resolved} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      </div>
    );
  }
  const initial = title.trim()[0]?.toUpperCase() ?? '?';
  // Stable hue from the title's first code point — soft two-stop gradient.
  const hue = ((title.charCodeAt(0) || 0) * 17) % 360;
  return (
    <div
      className="avatar"
      style={{
        ...base,
        background: `linear-gradient(135deg, oklch(0.55 0.12 ${hue}), oklch(0.35 0.1 ${hue + 40}))`,
        color: '#fff',
      }}
    >
      {initial}
    </div>
  );
}
