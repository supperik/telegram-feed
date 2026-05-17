import { createFileRoute } from '@tanstack/react-router';
import { FeedScreen } from '@/features/feed/FeedScreen';

export const Route = createFileRoute('/')({
  component: FeedScreen,
});
