import axios, { type AxiosInstance, type AxiosRequestConfig } from "axios";
import { useAuthStore } from "../auth/store";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const apiClient: AxiosInstance = axios.create({ baseURL });

apiClient.interceptors.request.use((cfg) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    cfg.headers = cfg.headers ?? {};
    cfg.headers.Authorization = `Bearer ${token}`;
  }
  return cfg;
});

let refreshInFlight: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  const { refreshToken, setTokens, clear } = useAuthStore.getState();
  if (!refreshToken) return null;
  try {
    const { data } = await axios.post<{
      access_token: string;
      refresh_token: string;
    }>(`${baseURL}/admin/refresh`, { refresh_token: refreshToken });
    setTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    clear();
    return null;
  }
}

apiClient.interceptors.response.use(
  (r) => r,
  async (error) => {
    const status = error?.response?.status;
    const original = error?.config as AxiosRequestConfig & {
      _retried?: boolean;
    };
    if (status === 401 && original && !original._retried) {
      original._retried = true;
      refreshInFlight ??= tryRefresh().finally(() => {
        refreshInFlight = null;
      });
      const newToken = await refreshInFlight;
      if (newToken) {
        original.headers = original.headers ?? {};
        (original.headers as Record<string, string>).Authorization =
          `Bearer ${newToken}`;
        return apiClient(original);
      }
    }
    return Promise.reject(error);
  },
);
