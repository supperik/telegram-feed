import { createFileRoute } from '@tanstack/react-router';
import { HiddenSourcesScreen } from '@/features/sources/HiddenSourcesScreen';

export const Route = createFileRoute('/sources/hidden')({
  component: HiddenSourcesScreen,
});
