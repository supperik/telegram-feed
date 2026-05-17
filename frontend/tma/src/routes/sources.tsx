import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/sources')({
  component: () => (
    <div className="p-4 text-center text-hint">Sources coming next phase.</div>
  ),
});
