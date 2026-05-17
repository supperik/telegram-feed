import { Link, useRouterState } from '@tanstack/react-router';

const tabs = [
  { to: '/', label: 'Feed' },
  { to: '/sources', label: 'Sources' },
] as const;

export function BottomNav() {
  const location = useRouterState({ select: (s) => s.location.pathname });
  return (
    <nav className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-2 border-t border-hint/20 bg-bg">
      {tabs.map((t) => {
        const active = location === t.to;
        return (
          <Link
            key={t.to}
            to={t.to}
            aria-current={active ? 'page' : undefined}
            className={`py-3 text-center text-sm ${active ? 'text-link font-semibold' : 'text-hint'}`}
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
