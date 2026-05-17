export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor({ code, message, status }: { code: string; message: string; status: number }) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }
}

export async function parseApiError(res: Response): Promise<ApiError> {
  let code = 'unknown';
  let message = res.statusText || `HTTP ${res.status}`;
  try {
    const body = (await res.json()) as unknown;
    if (body && typeof body === 'object' && 'error' in body) {
      const env = (body as { error: unknown }).error;
      if (env && typeof env === 'object') {
        const e = env as { code?: unknown; message?: unknown };
        if (typeof e.code === 'string') code = e.code;
        if (typeof e.message === 'string') message = e.message;
      }
    }
  } catch {
    // body wasn't JSON — keep generic
  }
  return new ApiError({ code, message, status: res.status });
}
