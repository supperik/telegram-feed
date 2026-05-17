import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { AddSourceForm } from '@/features/sources/AddSourceForm';
import { setTokens } from '@/features/auth/tokenStore';
import { server } from '../msw/server';

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe('AddSourceForm', () => {
  it('strips a leading @ and submits the username', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
    let received = '';
    server.use(
      http.post('http://test.local/sources', async ({ request }) => {
        received = ((await request.json()) as { username: string }).username;
        return HttpResponse.json({
          status: 'subscribed',
          channel: { id: 1, username: 'meduzaproject', title: 'M', photo_url: null },
          queue_id: null,
        });
      }),
    );
    render(<AddSourceForm />, { wrapper: wrap() });
    await userEvent.type(screen.getByPlaceholderText(/username/i), '@meduzaproject');
    await userEvent.click(screen.getByRole('button', { name: /add/i }));
    await screen.findByText(/subscribed/i);
    expect(received).toBe('meduzaproject');
  });

  it('renders the failure reason when queue fails', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
    let pollCount = 0;
    server.use(
      http.post('http://test.local/sources', () =>
        HttpResponse.json(
          { status: 'queued', channel: null, queue_id: 99 },
          { status: 202 },
        ),
      ),
      http.get('http://test.local/sources/queue/99', () => {
        pollCount += 1;
        return HttpResponse.json({
          queue_id: 99,
          status: pollCount < 2 ? 'pending' : 'failed',
          error_reason: 'username_not_occupied',
          channel: null,
        });
      }),
    );
    render(<AddSourceForm />, { wrapper: wrap() });
    await userEvent.type(screen.getByPlaceholderText(/username/i), 'doesnotexist');
    await userEvent.click(screen.getByRole('button', { name: /add/i }));
    await screen.findByText(/username_not_occupied/i, undefined, { timeout: 8000 });
  });
});
