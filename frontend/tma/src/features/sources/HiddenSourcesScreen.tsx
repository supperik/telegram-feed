import { Link } from '@tanstack/react-router';
import { HiddenSourceListItem } from '@/features/sources/HiddenSourceListItem';
import { useHiddenSources } from '@/features/sources/useHiddenSources';
import { SubHeader } from '@/shared/ui/SubHeader';
import { Spinner } from '@/shared/ui/Spinner';
import { ChevronLeftIcon } from '@/shared/ui/icons';

const NOTE_STYLE = {
  color: 'var(--hint)',
  font: '500 12px/1.5 var(--font-ui)',
  textAlign: 'center',
  padding: '12px 18px',
} as const;

export function HiddenSourcesScreen() {
  const hidden = useHiddenSources();
  const items = hidden.data?.items ?? [];

  return (
    <>
      <SubHeader
        title="Скрыты из ленты"
        back={
          <Link to="/sources" className="back" aria-label="К источникам">
            <ChevronLeftIcon size={16} />
          </Link>
        }
      />
      {hidden.status === 'pending' ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
          <Spinner />
        </div>
      ) : items.length === 0 ? (
        <p style={{ ...NOTE_STYLE, padding: '24px 18px', fontSize: 13 }}>Нет скрытых каналов.</p>
      ) : (
        <>
          <div className="tf-list" style={{ marginTop: 8 }}>
            {items.map((i) => (
              <HiddenSourceListItem key={i.channel.id} item={i} />
            ))}
          </div>
          <p style={NOTE_STYLE}>
            Каналы остаются в подписках, но их посты не появляются в ленте.
          </p>
        </>
      )}
    </>
  );
}
