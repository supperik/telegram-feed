import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

// eslint-disable-next-line react-refresh/only-export-components
const Root = () => (
  <div className="flex h-full items-center justify-center text-2xl font-semibold">
    Telegram Feed
  </div>
);

const container = document.getElementById('root');
if (!container) throw new Error('Missing #root');
createRoot(container).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
