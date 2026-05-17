import { SDKProvider, useThemeParams } from '@tma.js/sdk-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Outlet, createRootRoute } from '@tanstack/react-router';
import { useEffect } from 'react';
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

function ThemeSync() {
  // Initial-only sync: writes theme params to CSS vars once the SDK has them.
  // Telegram theme can change at runtime (light↔dark toggle); reacting to that
  // would require subscribing to the `theme` signal, which is out of MVP scope.
  const theme = useThemeParams();
  useEffect(() => {
    if (!theme) return;
    const state = theme.getState();
    for (const [key, cssVar] of Object.entries(themeToCssVars)) {
      const v = state[key];
      if (v) document.documentElement.style.setProperty(cssVar, v);
    }
  }, [theme]);
  return null;
}

function Gate() {
  const { status, error, retry } = useAuth();
  if (status === 'bootstrapping') {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );
  }
  if (status === 'failed') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-6">
        <div className="text-center text-hint">{error ?? 'Authentication failed'}</div>
        <Button onClick={retry}>Retry</Button>
      </div>
    );
  }
  return (
    <>
      <div className="flex-1 overflow-y-auto pb-16">
        <Outlet />
      </div>
      <BottomNav />
    </>
  );
}

export const Route = createRootRoute({
  component: () => (
    <SDKProvider acceptCustomStyles>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ThemeSync />
          <Gate />
        </AuthProvider>
      </QueryClientProvider>
    </SDKProvider>
  ),
});
