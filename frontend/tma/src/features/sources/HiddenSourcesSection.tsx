import { useHiddenSources } from '@/features/sources/useHiddenSources';
import { HiddenSourceListItem } from '@/features/sources/HiddenSourceListItem';
import { ChevronDownIcon } from '@/shared/ui/icons';

export function HiddenSourcesSection() {
  const { data, status } = useHiddenSources();

  if (status !== 'success') return null;
  if (data.items.length === 0) return null;

  return (
    <section className="mx-3 mt-3 mb-20">
      <details className="rounded-2xl bg-secondary shadow-card">
        <summary className="flex cursor-pointer select-none items-center justify-between px-3 py-2.5 text-sm font-semibold">
          <span>Скрыты из ленты ({data.items.length})</span>
          <ChevronDownIcon size={16} className="text-hint" />
        </summary>
        <ul>
          {data.items.map((i) => (
            <HiddenSourceListItem key={i.channel.id} item={i} />
          ))}
        </ul>
      </details>
    </section>
  );
}
