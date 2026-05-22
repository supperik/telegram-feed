import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { IconButton } from '@/shared/ui/IconButton';
import { RefreshIcon } from '@/shared/ui/icons';

describe('IconButton', () => {
  it('renders the icon child', () => {
    render(
      <IconButton aria-label="refresh">
        <RefreshIcon />
      </IconButton>,
    );
    expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
  });

  it('calls onClick when pressed', async () => {
    const onClick = vi.fn();
    render(
      <IconButton aria-label="refresh" onClick={onClick}>
        <RefreshIcon />
      </IconButton>,
    );
    await userEvent.click(screen.getByRole('button', { name: /refresh/i }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('respects disabled', async () => {
    const onClick = vi.fn();
    render(
      <IconButton aria-label="r" onClick={onClick} disabled>
        <RefreshIcon />
      </IconButton>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'r' }));
    expect(onClick).not.toHaveBeenCalled();
  });

  it('supports "danger" variant', () => {
    render(
      <IconButton aria-label="del" variant="danger">
        <RefreshIcon />
      </IconButton>,
    );
    expect(screen.getByRole('button', { name: 'del' })).toHaveAttribute('data-variant', 'danger');
  });
});
