import { Link, useRouterState } from '@tanstack/react-router';
import type { ComponentType, CSSProperties } from 'react';
import { BookmarkIcon, GridIcon, HomeIcon } from './icons';

interface Tab {
  to: '/' | '/saved' | '/sources';
  label: string;
  Icon: ComponentType<{ size?: number; className?: string }>;
}

const tabs: Tab[] = [
  { to: '/', label: 'Лента', Icon: HomeIcon },
  { to: '/saved', label: 'Сохранёнки', Icon: BookmarkIcon },
  { to: '/sources', label: 'Источники', Icon: GridIcon },
];

export function BottomNav() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const activeIdx = Math.max(
    0,
    tabs.findIndex((t) => (t.to === '/' ? pathname === '/' : pathname.startsWith(t.to))),
  );
  // CSS custom props drive the sliding pill — typed via an index signature.
  const pillStyle: CSSProperties & Record<string, string | number> = {
    '--idx': activeIdx,
    '--count': tabs.length,
  };
  return (
    <nav className="tf-tabbar">
      <div className="tf-tab-pill" style={pillStyle} />
      {tabs.map(({ to, label, Icon }, i) => (
        <Link
          key={to}
          to={to}
          className="tf-tab"
          data-active={i === activeIdx}
          aria-current={i === activeIdx ? 'page' : undefined}
        >
          <Icon size={22} />
          <span>{label}</span>
        </Link>
      ))}
    </nav>
  );
}
