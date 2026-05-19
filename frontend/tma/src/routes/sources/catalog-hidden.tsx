import { createFileRoute } from '@tanstack/react-router';
import { HiddenCatalogScreen } from '@/features/sources/HiddenCatalogScreen';

export const Route = createFileRoute('/sources/catalog-hidden')({
  component: HiddenCatalogScreen,
});
