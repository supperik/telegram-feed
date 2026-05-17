import { useLaunchParams } from '@tma.js/sdk-react';
import { createContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { apiPost } from '@/shared/api/client';
import { getTokens, setTokens } from '@/features/auth/tokenStore';
import type { TokenPair } from '@/shared/api/types';

// NOTE: deviation from the plan's pseudocode.
// Plan used `useRawInitData()` from `@tma.js/sdk-react`, but the installed SDK
// (`@tma.js/sdk-react@2.2.8` over `@tma.js/sdk@2.7.0`) exposes:
//   - `useInitDataRaw()` → returns `SDKContextItem<InitData | undefined>` (NOT a raw string)
//   - `useLaunchParams()` → returns `LaunchParams` with `initDataRaw: string | undefined`
// The cleanest equivalent of "raw initData string from the SDK" in this version
// is `useLaunchParams().initDataRaw`.

type AuthStatus = 'bootstrapping' | 'authenticated' | 'failed';

export interface AuthContextValue {
  status: AuthStatus;
  error: string | null;
  retry: () => void;
}

// eslint-disable-next-line react-refresh/only-export-components -- co-located with AuthProvider on purpose; consumed by useAuth in a separate file.
export const AuthContext = createContext<AuthContextValue | null>(null);

interface Props {
  children: ReactNode;
}

export function AuthProvider({ children }: Props) {
  const launchParams = useLaunchParams();
  const rawInitData = launchParams.initDataRaw;
  const [status, setStatus] = useState<AuthStatus>(() =>
    getTokens() ? 'authenticated' : 'bootstrapping',
  );
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    if (getTokens()) {
      setStatus('authenticated');
      return;
    }
    if (!rawInitData) {
      setStatus('failed');
      setError('Telegram launch parameters missing');
      return;
    }
    setStatus('bootstrapping');
    apiPost<TokenPair>('/auth/telegram', { init_data: rawInitData }, { anonymous: true })
      .then((pair) => {
        if (cancelled) return;
        setTokens(pair);
        setStatus('authenticated');
        setError(null);
      })
      .catch((e: Error) => {
        if (cancelled) return;
        setStatus('failed');
        setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [rawInitData, attempt]);

  const value = useMemo<AuthContextValue>(
    () => ({ status, error, retry: () => setAttempt((n) => n + 1) }),
    [status, error],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
