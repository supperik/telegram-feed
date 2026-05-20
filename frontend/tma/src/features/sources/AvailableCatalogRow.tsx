import { CatalogChannelItem } from '@/features/sources/CatalogChannelItem';
import { useSubscribeByChannelId } from '@/features/sources/useChannelCatalog';
import type { CatalogChannelItem as Item } from '@/shared/api/types';

interface Props {
  item: Item;
  onHide: (channelId: number) => void;
}

/**
 * One "available" catalog row. Owns a per-channel subscribe hook so each row
 * tracks its own queued/polling state independently of its neighbours.
 */
export function AvailableCatalogRow({ item, onHide }: Props) {
  const { subscribe, state } = useSubscribeByChannelId(item.channel.id);
  return (
    <CatalogChannelItem
      item={item}
      actions="available"
      subscribeState={state}
      onSubscribe={subscribe}
      onHide={onHide}
    />
  );
}
