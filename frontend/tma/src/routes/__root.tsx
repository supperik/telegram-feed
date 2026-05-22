import { SDKProvider, useThemeParams } from '@tma.js/sdk-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Outlet, createRootRoute, useRouterState } from '@tanstack/react-router';
import { useEffect, useRef, useState } from 'react';
import { AuthProvider } from '@/features/auth/AuthProvider';
import { useAuth } from '@/features/auth/useAuth';
import { BottomNav } from '@/shared/ui/BottomNav';
import { Button } from '@/shared/ui/Button';
import { Spinner } from '@/shared/ui/Spinner';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, refetchOnWindowFocus: true, retry: 1 },
    mutations: { retry: 0 },
  },
});

// NOTE: deviation from the plan's pseudocode.
// The plan listed snake_case keys (`bg_color`, `text_color`, …) for the theme
// params map. The installed `@tma.js/sdk@2.7.0` exposes `ThemeParamsParsed`
// with camelCase keys (`bgColor`, `textColor`, …). We also call
// `.getState()` on the `ThemeParams` instance returned by `useThemeParams()`
// to obtain a plain enumerable object — the class itself exposes values via
// getters that `Object.entries` would not enumerate.
const themeToCssVars: Record<string, string> = {
  bgColor: '--tg-bg',
  textColor: '--tg-text',
  hintColor: '--tg-hint',
  linkColor: '--tg-link',
  buttonColor: '--tg-button',
  buttonTextColor: '--tg-button-text',
  secondaryBgColor: '--tg-secondary-bg',
};

// Perceived lightness of a #rrggbb string (Rec. 601 luma). Telegram theme
// params arrive as hex; the design's token set has a dark and a light
// variant — we pick which by the background colour. Defaults to dark.
function isHexDark(hex: string): boolean {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  const group = m?.[1];
  if (!group) return true;
  const n = parseInt(group, 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255 < 0.5;
}

// Initial-only sync: writes theme params to CSS vars once the SDK has them
// and reports light/dark. Telegram theme can change at runtime (light↔dark
// toggle); reacting to that would require subscribing to the `theme` signal,
// which is out of MVP scope — `useThemeParams()` returns a stable instance.
function useTelegramTheme(): 'dark' | 'light' {
  const theme = useThemeParams();
  const [mode, setMode] = useState<'dark' | 'light'>('dark');
  useEffect(() => {
    if (!theme) return;
    const state = theme.getState();
    for (const [key, cssVar] of Object.entries(themeToCssVars)) {
      const v = state[key];
      if (v) document.documentElement.style.setProperty(cssVar, v);
    }
    if (state.bgColor) setMode(isHexDark(state.bgColor) ? 'dark' : 'light');
  }, [theme]);
  return mode;
}

function Gate() {
  const { status, error, retry } = useAuth();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const scrollRef = useRef<HTMLDivElement>(null);
  // Reset the shared scroll container on every route change — otherwise a
  // hard fling keeps its momentum after the route swaps under it, and the
  // next tab opens already mid-scroll.
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [pathname]);

  if (status === 'bootstrapping') {
    return (
      <div className="tf-fullcenter">
        <Spinner />
      </div>
    );
  }
  if (status === 'failed') {
    return (
      <div className="tf-fullcenter" style={{ flexDirection: 'column', gap: 16 }}>
        <div style={{ textAlign: 'center', color: 'var(--hint)' }}>
          {error ?? 'Не удалось авторизоваться'}
        </div>
        <Button onClick={retry}>Повторить</Button>
      </div>
    );
  }
  return (
    <>
      <div ref={scrollRef} className="tf-scroll">
        <Outlet />
      </div>
      <BottomNav />
    </>
  );
}

function Shell() {
  const mode = useTelegramTheme();
  return (
    <div className="tf-app" data-theme={mode}>
      <AuthProvider>
        <Gate />
      </AuthProvider>
    </div>
  );
}

export const Route = createRootRoute({
  component: () => (
    <SDKProvider acceptCustomStyles>
      <QueryClientProvider client={queryClient}>
        <Shell />
      </QueryClientProvider>
    </SDKProvider>
  ),
});
