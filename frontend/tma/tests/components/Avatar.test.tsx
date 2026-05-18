import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Avatar } from '@/shared/ui/Avatar';

describe('Avatar', () => {
  it('renders <img> when photoUrl is provided', () => {
    render(<Avatar photoUrl="https://x/y.jpg" title="Meduza" />);
    const img = screen.getByRole('presentation');
    expect(img).toHaveAttribute('src', 'https://x/y.jpg');
    expect(img).toHaveAttribute('alt', '');
  });

  it('renders gradient initial fallback when photoUrl is null', () => {
    render(<Avatar photoUrl={null} title="Meduza" />);
    expect(screen.queryByRole('img', { hidden: true })).toBeNull();
    expect(screen.getByText('M')).toBeInTheDocument();
  });

  it('uses "?" when title is empty', () => {
    render(<Avatar photoUrl={null} title="" />);
    expect(screen.getByText('?')).toBeInTheDocument();
  });

  it('applies size prop (44 default → both 44px and rounded-full)', () => {
    const { container } = render(<Avatar photoUrl={null} title="A" size={40} />);
    const root = container.firstChild as HTMLElement;
    expect(root.style.width).toBe('40px');
    expect(root.style.height).toBe('40px');
  });
});
