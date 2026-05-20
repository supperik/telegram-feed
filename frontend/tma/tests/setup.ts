import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { server } from './msw/server';

// Pin a stable API base URL for tests so MSW URL patterns match.
// Use `.local` rather than a bare `test` so tough-cookie inside MSW does not reject
// the host as a public-suffix special-use domain.
import.meta.env.VITE_API_BASE_URL = 'http://test.local';

// jsdom has no IntersectionObserver; feed cards use it for read-tracking
// (usePostRead). Tests that need to drive it stub their own.
class IntersectionObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}
globalThis.IntersectionObserver =
  IntersectionObserverStub as unknown as typeof IntersectionObserver;

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  localStorage.clear();
});
afterAll(() => server.close());
