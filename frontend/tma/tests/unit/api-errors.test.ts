import { describe, expect, it } from 'vitest';
import { ApiError, parseApiError } from '@/shared/api/errors';

describe('parseApiError', () => {
  it('extracts code and message from envelope', async () => {
    const res = new Response(
      JSON.stringify({ error: { code: 'bad_init_data', message: 'Signature mismatch' } }),
      { status: 401, headers: { 'content-type': 'application/json' } },
    );
    const err = await parseApiError(res);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe('bad_init_data');
    expect(err.status).toBe(401);
    expect(err.message).toBe('Signature mismatch');
  });

  it('falls back to generic code when body is not JSON', async () => {
    const res = new Response('oops', { status: 500 });
    const err = await parseApiError(res);
    expect(err.code).toBe('unknown');
    expect(err.status).toBe(500);
  });
});
