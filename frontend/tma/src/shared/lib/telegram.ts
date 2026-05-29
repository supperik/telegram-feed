import { mockTelegramEnv } from '@tma.js/sdk-react';

import type { FeedChannel } from '@/shared/api/types';

// Build the canonical t.me URL for a feed post.
// Public channel: t.me/<username>/<msg>.
// Private channel: t.me/c/<tg_chat_id>/<msg>. tg_chat_id is stored as the
// raw positive supergroup id (e.g. 1319248631), which is exactly the form
// Telegram expects in the c/ path.
export function tgPostUrl(
  channel: Pick<FeedChannel, 'username' | 'tg_chat_id'>,
  tgMessageId: number,
): string {
  return channel.username
    ? `https://t.me/${channel.username}/${tgMessageId}`
    : `https://t.me/c/${channel.tg_chat_id}/${tgMessageId}`;
}

interface SafeAreaInset {
  top?: number;
  right?: number;
  bottom?: number;
  left?: number;
}

interface TelegramWebApp {
  // "unknown" in a plain browser; a concrete value ('ios', 'android',
  // 'tdesktop', …) only inside a real Telegram client.
  platform?: string;
  openTelegramLink?: (url: string) => void;
  ready?: () => void;
  expand?: () => void;
  isVersionAtLeast?: (version: string) => boolean;
  requestFullscreen?: () => void;
  onEvent?: (event: string, handler: () => void) => void;
  contentSafeAreaInset?: SafeAreaInset;
}

function getWebApp(): TelegramWebApp | undefined {
  return (window as unknown as { Telegram?: { WebApp?: TelegramWebApp } })?.Telegram
    ?.WebApp;
}

// Inside Telegram, plain <a href="https://t.me/..."> click navigates the
// WebView instead of opening the post in the Telegram client — the WebApp
// SDK's openTelegramLink is what makes the client take over. Outside the
// WebView (browser dev) we fall back to a regular new-tab open so the link
// still works.
export function openTelegramLink(url: string): void {
  const wa = getWebApp();
  if (wa?.openTelegramLink) {
    wa.openTelegramLink(url);
    return;
  }
  window.open(url, '_blank', 'noopener,noreferrer');
}

// NOTE: deviation from the plan's pseudocode.
// The plan's snippet imports a top-level `init` from `@tma.js/sdk-react` and
// uses an outer `launchParams` envelope when calling `mockTelegramEnv`. Those
// shapes belong to a newer SDK revision. The installed `@tma.js/sdk@2.7.0`
// only exposes web-environment-specific `initWeb` (which throws outside
// Telegram) and `mockTelegramEnv` accepts a flat `LaunchParams` object directly.
// We therefore drop the global `init()` call (SDK components self-initialise
// when their hooks subscribe) and pass the launch parameters flat.

// In fullscreen the WebView spans the whole screen and Telegram draws its own
// controls (close / ⋯ menu, top-right) floating over our content.
// contentSafeAreaInset is the room they need — expose its top as a CSS var the
// layout pads for. The device notch is handled separately by
// env(safe-area-inset-top).
function syncContentSafeArea(wa: TelegramWebApp): void {
  const apply = (): void => {
    const top = wa.contentSafeAreaInset?.top ?? 0;
    document.documentElement.style.setProperty('--tf-content-safe-top', `${top}px`);
  };
  apply();
  wa.onEvent?.('contentSafeAreaChanged', apply);
  wa.onEvent?.('fullscreenChanged', apply);
}

let booted = false;

export function bootTelegram(): void {
  if (booted) return;
  booted = true;

  const wa = getWebApp();
  // telegram-web-app.js creates window.Telegram.WebApp everywhere it loads;
  // only a real client reports a concrete platform.
  if (wa && wa.platform !== 'unknown') {
    wa.ready?.();
    // expand() gives full height on every client; requestFullscreen() (Bot API
    // 8.0) additionally covers the status bar on mobile. Older/desktop clients
    // fail the version guard and keep the expanded-but-windowed layout.
    wa.expand?.();
    if (wa.isVersionAtLeast?.('8.0')) {
      wa.requestFullscreen?.();
      syncContentSafeArea(wa);
    }
    return;
  }

  // Not inside Telegram (e.g. local browser dev): install a mock environment so
  // SDK hooks return deterministic values. The mock is intentionally invalid
  // for real auth — local backends should bypass HMAC verification or use a dev
  // bot token.
  if (import.meta.env.DEV) {
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
