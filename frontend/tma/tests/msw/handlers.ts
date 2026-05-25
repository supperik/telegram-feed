import { http, HttpResponse, type HttpHandler } from 'msw';

export const baseUrl = 'http://test.local';

// Default: a minimal handler set. Each test installs what it actually needs
// via `server.use(...)`, but a few generic GETs (called by hooks mounted on
// many screens) live here to keep the test output free of unhandled-request
// warnings.
export const handlers: HttpHandler[] = [
  http.get(`${baseUrl}/channels/categories`, () =>
    HttpResponse.json({ categories: [] }),
  ),
];
