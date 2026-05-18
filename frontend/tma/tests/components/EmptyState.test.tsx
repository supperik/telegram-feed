import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { EmptyState } from '@/shared/ui/EmptyState';
import { AlertCircleIcon } from '@/shared/ui/icons';

describe('EmptyState', () => {
  it('renders icon, title, body and optional CTA', async () => {
    const onAction = vi.fn();
    render(
      <EmptyState
        icon={<AlertCircleIcon />}
        title="Лента пока пуста"
        body="Добавьте каналы — будут появляться посты."
        actionLabel="Добавить каналы →"
        onAction={onAction}
      />,
    );
    expect(screen.getByText('Лента пока пуста')).toBeInTheDocument();
    expect(screen.getByText(/Добавьте каналы/)).toBeInTheDocument();
    const btn = screen.getByRole('button', { name: /добавить каналы/i });
    await userEvent.click(btn);
    expect(onAction).toHaveBeenCalledOnce();
  });

  it('renders without CTA when actionLabel is not provided', () => {
    render(<EmptyState icon={<AlertCircleIcon />} title="x" body="y" />);
    expect(screen.queryByRole('button')).toBeNull();
  });
});
