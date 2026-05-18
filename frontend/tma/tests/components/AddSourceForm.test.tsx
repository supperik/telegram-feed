import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { AddSourceForm } from '@/features/sources/AddSourceForm';
import { setTokens } from '@/features/auth/tokenStore';
import { server } from '../msw/server';

const API_BASE = 'http://test.local';

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

function authenticate() {
  setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
}

describe('AddSourceForm', () => {
  it('submits @username as-is via {input} field (regression)', async () => {
    authenticate();
    let captured: { input?: string } = {};
    server.use(
      http.post(`${API_BASE}/sources`, async ({ request }) => {
        captured = (await request.json()) as { input: string };
        return HttpResponse.json({
          status: 'subscribed',
          channel: { id: 1, username: 'meduzaproject', title: 'M', photo_url: null, is_private: false },
          queue_id: null,
        });
      }),
    );
    render(<AddSourceForm />, { wrapper: wrap() });
    await userEvent.type(screen.getByPlaceholderText(/@username/i), '@meduzaproject');
    await userEvent.click(screen.getByRole('button', { name: /подписаться/i }));
    await screen.findByText(/готово/i);
    // Form no longer strips '@' — server-side parser handles all input shapes.
    expect(captured.input).toBe('@meduzaproject');
  });

  it('submits invite link unchanged in body.input', async () => {
    authenticate();
    let captured: { input?: string } = {};
    server.use(
      http.post(`${API_BASE}/sources`, async ({ request }) => {
        captured = (await request.json()) as { input: string };
        return HttpResponse.json(
          { status: 'queued', channel: null, queue_id: 7 },
          { status: 202 },
        );
      }),
      http.get(`${API_BASE}/sources/queue/7`, () =>
        HttpResponse.json({
          queue_id: 7,
          status: 'done',
          error_code: null,
          error_reason: null,
          channel: { id: 1, username: null, title: 'Secret', photo_url: null, is_private: true },
        }),
      ),
    );
    render(<AddSourceForm />, { wrapper: wrap() });
    await userEvent.type(screen.getByPlaceholderText(/@username/i), 'https://t.me/+abcDEF_123');
    await userEvent.click(screen.getByRole('button', { name: /подписаться/i }));
    await waitFor(() => expect(captured).toEqual({ input: 'https://t.me/+abcDEF_123' }));
  });

  it('shows localized message on invite_expired error_code', async () => {
    authenticate();
    server.use(
      http.post(`${API_BASE}/sources`, () =>
        HttpResponse.json({ status: 'queued', channel: null, queue_id: 9 }, { status: 202 }),
      ),
      http.get(`${API_BASE}/sources/queue/9`, () =>
        HttpResponse.json({
          queue_id: 9,
          status: 'failed',
          error_code: 'invite_expired',
          error_reason: null,
          channel: null,
        }),
      ),
    );
    render(<AddSourceForm />, { wrapper: wrap() });
    await userEvent.type(screen.getByPlaceholderText(/@username/i), 'https://t.me/+abc');
    await userEvent.click(screen.getByRole('button', { name: /подписаться/i }));
    await waitFor(
      () => expect(screen.getByText(/ссылка истекла/i)).toBeInTheDocument(),
      { timeout: 8000 },
    );
  });

  it('shows pending_approval message', async () => {
    authenticate();
    server.use(
      http.post(`${API_BASE}/sources`, () =>
        HttpResponse.json({ status: 'queued', channel: null, queue_id: 11 }, { status: 202 }),
      ),
      http.get(`${API_BASE}/sources/queue/11`, () =>
        HttpResponse.json({
          queue_id: 11,
          status: 'pending_approval',
          error_code: null,
          error_reason: null,
          channel: null,
        }),
      ),
    );
    render(<AddSourceForm />, { wrapper: wrap() });
    await userEvent.type(screen.getByPlaceholderText(/@username/i), 'https://t.me/+abc');
    await userEvent.click(screen.getByRole('button', { name: /подписаться/i }));
    await waitFor(
      () => expect(screen.getByText(/заявка отправлена/i)).toBeInTheDocument(),
      { timeout: 8000 },
    );
  });

  it('renders a localized failure message when queue fails with error_code', async () => {
    authenticate();
    let pollCount = 0;
    server.use(
      http.post(`${API_BASE}/sources`, () =>
        HttpResponse.json({ status: 'queued', channel: null, queue_id: 99 }, { status: 202 }),
      ),
      http.get(`${API_BASE}/sources/queue/99`, () => {
        pollCount += 1;
        return HttpResponse.json({
          queue_id: 99,
          status: pollCount < 2 ? 'pending' : 'failed',
          error_code: 'username_not_occupied',
          error_reason: null,
          channel: null,
        });
      }),
    );
    render(<AddSourceForm />, { wrapper: wrap() });
    await userEvent.type(screen.getByPlaceholderText(/@username/i), 'doesnotexist');
    await userEvent.click(screen.getByRole('button', { name: /подписаться/i }));
    await screen.findByText(/канал с таким username не найден/i, undefined, { timeout: 8000 });
  });
});
