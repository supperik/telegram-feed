import { createFileRoute } from '@tanstack/react-router';
import { HiddenCatalogScreen } from '@/features/sources/HiddenCatalogScreen';

export const Route = createFileRoute('/sources/hidden')({
  component: HiddenCatalogScreen,
});
