import { createFileRoute } from '@tanstack/react-router';
import { BookmarkIcon } from '@/shared/ui/icons';
import { EmptyState } from '@/shared/ui/EmptyState';

function SavedPlaceholder() {
  return (
    <div>
      <header className="px-4 pb-1 pt-3">
        <h1 className="text-2xl font-bold tracking-tight">Сохранёнки</h1>
        <div className="mt-0.5 text-xs text-hint">временно недоступно</div>
      </header>
      <EmptyState
        icon={<BookmarkIcon />}
        title="Скоро здесь будут сохранённые посты"
        body="Бэкенд этой вкладки ещё подключают. Пока сохранение работает в Ленте — просто нажимайте 🔖."
      />
    </div>
  );
}

export const Route = createFileRoute('/saved')({
  component: SavedPlaceholder,
});
