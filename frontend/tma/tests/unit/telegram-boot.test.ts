import { afterEach, describe, expect, it, vi } from 'vitest';

// telegram.ts imports mockTelegramEnv from the SDK; stub it so booting in tests
// never touches the real SDK transport.
vi.mock('@tma.js/sdk-react', () => ({ mockTelegramEnv: vi.fn() }));

interface WebAppMock {
  platform: string;
  ready: () => void;
  expand: () => void;
  isVersionAtLeast: (version: string) => boolean;
  requestFullscreen: () => void;
  onEvent: (event: string, handler: () => void) => void;
  contentSafeAreaInset: { top: number; right: number; bottom: number; left: number };
}

function installWebApp(over: Partial<WebAppMock> = {}): WebAppMock {
  const wa: WebAppMock = {
    platform: 'ios',
    ready: vi.fn(),
    expand: vi.fn(),
    isVersionAtLeast: vi.fn(() => true),
    requestFullscreen: vi.fn(),
    onEvent: vi.fn(),
    contentSafeAreaInset: { top: 0, right: 0, bottom: 0, left: 0 },
    ...over,
  };
  (window as unknown as { Telegram: { WebApp: WebAppMock } }).Telegram = { WebApp: wa };
  return wa;
}

// bootTelegram guards itself with a module-level `booted` flag, so each scenario
// needs a fresh module instance.
async function boot(): Promise<void> {
  vi.resetModules();
  const mod = await import('@/shared/lib/telegram');
  mod.bootTelegram();
}

afterEach(() => {
  delete (window as unknown as { Telegram?: unknown }).Telegram;
  document.documentElement.style.removeProperty('--tf-content-safe-top');
  vi.restoreAllMocks();
});

describe('bootTelegram — fullscreen launch', () => {
  it('requests fullscreen on a Telegram client supporting Bot API 8.0', async () => {
    const wa = installWebApp();
    await boot();
    expect(wa.ready).toHaveBeenCalled();
    expect(wa.expand).toHaveBeenCalled();
    expect(wa.requestFullscreen).toHaveBeenCalledTimes(1);
  });

  it('expands but does not request fullscreen on pre-8.0 clients', async () => {
    const wa = installWebApp({ isVersionAtLeast: vi.fn(() => false) });
    await boot();
    expect(wa.expand).toHaveBeenCalled();
    expect(wa.requestFullscreen).not.toHaveBeenCalled();
  });

  it('leaves the WebApp untouched outside Telegram (platform "unknown")', async () => {
    const wa = installWebApp({ platform: 'unknown' });
    await boot();
    expect(wa.ready).not.toHaveBeenCalled();
    expect(wa.expand).not.toHaveBeenCalled();
    expect(wa.requestFullscreen).not.toHaveBeenCalled();
  });

  it('publishes the content safe-area top inset as --tf-content-safe-top in fullscreen', async () => {
    installWebApp({ contentSafeAreaInset: { top: 24, right: 0, bottom: 0, left: 0 } });
    await boot();
    expect(document.documentElement.style.getPropertyValue('--tf-content-safe-top')).toBe('24px');
  });
});
