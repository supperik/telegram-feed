import { useSources } from '@/features/sources/useSources';
import { AddSourceForm } from '@/features/sources/AddSourceForm';
import { SourceListItem } from '@/features/sources/SourceListItem';
import { Spinner } from '@/shared/ui/Spinner';

export function SourcesScreen() {
  const { data, status } = useSources();
  if (status === 'pending') {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );
  }
  if (status === 'error') {
    return <div className="p-6 text-center text-hint">Could not load sources.</div>;
  }

  return (
    <div>
      <AddSourceForm />
      {data.items.length === 0 ? (
        <div className="p-6 text-center text-hint">
          No sources yet. Add a public channel above.
        </div>
      ) : (
        <ul>
          {data.items.map((i) => (
            <SourceListItem key={i.channel.id} item={i} />
          ))}
        </ul>
      )}
    </div>
  );
}
