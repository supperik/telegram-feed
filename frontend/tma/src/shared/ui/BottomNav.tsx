import { Link, useRouterState } from '@tanstack/react-router';
import type { ComponentType } from 'react';
import { BookmarkIcon, GridIcon, HomeIcon } from '@/shared/ui/icons';

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
  return (
    <nav className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-3 border-t border-black/10 bg-bg">
      {tabs.map(({ to, label, Icon }) => {
        const active = pathname === to;
        return (
          <Link
            key={to}
            to={to}
            aria-current={active ? 'page' : undefined}
            className={`flex flex-col items-center gap-1 py-2 text-[11px] ${active ? 'text-link' : 'text-hint'}`}
          >
            <Icon size={22} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
