import { createFileRoute } from '@tanstack/react-router';
import { SavedScreen } from '@/features/saved/SavedScreen';

export const Route = createFileRoute('/saved')({
  component: SavedScreen,
});
