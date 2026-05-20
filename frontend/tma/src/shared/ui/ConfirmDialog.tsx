interface TelegramWebApp {
  showConfirm?: (message: string, callback: (confirmed: boolean) => void) => void;
}

export const ConfirmDialog = {
  // Telegram's WebView throttles the native window.confirm() after a few calls
  // and then returns false instantly without rendering anything — the delete
  // button would silently do nothing. WebApp.showConfirm is the platform dialog
  // and isn't throttled. Outside the WebView (browser dev, tests) there is no
  // WebApp, so fall back to window.confirm.
  confirm(message: string): Promise<boolean> {
    const wa = (window as unknown as { Telegram?: { WebApp?: TelegramWebApp } })
      .Telegram?.WebApp;
    if (wa?.showConfirm) {
      return new Promise<boolean>((resolve) => {
        wa.showConfirm!(message, (confirmed) => resolve(confirmed));
      });
    }
    return Promise.resolve(window.confirm(message));
  },
};
