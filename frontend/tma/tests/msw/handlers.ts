import type { HttpHandler } from 'msw';

export const baseUrl = 'http://test.local';

// Default: empty handler list — each test installs what it needs via server.use().
export const handlers: HttpHandler[] = [];
