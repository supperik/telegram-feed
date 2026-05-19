import { createFileRoute } from '@tanstack/react-router';
import { SourcesScreen } from '@/features/sources/SourcesScreen';

export const Route = createFileRoute('/sources/')({
  component: SourcesScreen,
});
