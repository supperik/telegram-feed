import { afterEach, describe, expect, it, vi } from 'vitest';
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog';

type WindowWithTelegram = typeof window & {
  Telegram?: { WebApp?: { showConfirm?: unknown } };
};

afterEach(() => {
  vi.restoreAllMocks();
  delete (window as WindowWithTelegram).Telegram;
});

describe('ConfirmDialog', () => {
  it('uses Telegram WebApp.showConfirm inside the WebView, not window.confirm', async () => {
    const showConfirm = vi.fn((_message: string, cb: (ok: boolean) => void) => cb(true));
    (window as WindowWithTelegram).Telegram = { WebApp: { showConfirm } };
    const nativeConfirm = vi.spyOn(window, 'confirm').mockReturnValue(false);

    await expect(ConfirmDialog.confirm('Удалить?')).resolves.toBe(true);
    expect(showConfirm).toHaveBeenCalledWith('Удалить?', expect.any(Function));
    expect(nativeConfirm).not.toHaveBeenCalled();
  });

  it('resolves false when the user cancels in showConfirm', async () => {
    const showConfirm = vi.fn((_message: string, cb: (ok: boolean) => void) => cb(false));
    (window as WindowWithTelegram).Telegram = { WebApp: { showConfirm } };

    await expect(ConfirmDialog.confirm('Удалить?')).resolves.toBe(false);
  });

  it('falls back to window.confirm outside the Telegram WebView', async () => {
    const nativeConfirm = vi.spyOn(window, 'confirm').mockReturnValue(true);

    await expect(ConfirmDialog.confirm('Удалить?')).resolves.toBe(true);
    expect(nativeConfirm).toHaveBeenCalledWith('Удалить?');
  });
});
