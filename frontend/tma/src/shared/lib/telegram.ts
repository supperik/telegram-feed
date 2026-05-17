import { mockTelegramEnv } from '@tma.js/sdk-react';

// NOTE: deviation from the plan's pseudocode.
// The plan's snippet imports a top-level `init` from `@tma.js/sdk-react` and
// uses an outer `launchParams` envelope when calling `mockTelegramEnv`. Those
// shapes belong to a newer SDK revision. The installed `@tma.js/sdk@2.7.0`
// only exposes web-environment-specific `initWeb` (which throws outside
// Telegram) and `mockTelegramEnv` accepts a flat `LaunchParams` object directly.
// We therefore drop the global `init()` call (SDK components self-initialise
// when their hooks subscribe) and pass the launch parameters flat.

let booted = false;

export function bootTelegram(): void {
  if (booted) return;
  booted = true;

  // If we're not running inside Telegram (e.g. local browser dev), install a
  // mock environment so SDK hooks return deterministic values. The mock is
  // intentionally invalid for real auth — local backends should bypass HMAC
  // verification or use a dev bot token.
  const insideTelegram =
    typeof window !== 'undefined' &&
    Boolean((window as unknown as { Telegram?: { WebApp?: unknown } }).Telegram?.WebApp);

  if (!insideTelegram && import.meta.env.DEV) {
    const initDataRaw = new URLSearchParams([
      ['user', JSON.stringify({ id: 1, first_name: 'Dev', username: 'dev' })],
      ['auth_date', Math.floor(Date.now() / 1000).toString()],
      ['hash', 'dev-bypass'],
    ]).toString();

    mockTelegramEnv({
      initDataRaw,
      platform: 'web',
      version: '8.0',
      themeParams: {
        bgColor: '#ffffff',
        textColor: '#000000',
        hintColor: '#6d7780',
        linkColor: '#1d6cd1',
        buttonColor: '#1d6cd1',
        buttonTextColor: '#ffffff',
        secondaryBgColor: '#f4f4f5',
      },
    });
  }
}
