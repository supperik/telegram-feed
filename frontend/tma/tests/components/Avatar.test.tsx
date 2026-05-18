import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { setTokens, clearTokens } from '@/features/auth/tokenStore';
import { Avatar } from '@/shared/ui/Avatar';

describe('Avatar', () => {
  afterEach(() => clearTokens());

  it('renders <img> with absolute photoUrl unchanged', () => {
    render(<Avatar photoUrl="https://x/y.jpg" title="Meduza" />);
    const img = screen.getByRole('presentation');
    expect(img).toHaveAttribute('src', 'https://x/y.jpg');
    expect(img).toHaveAttribute('alt', '');
  });

  it('appends ?token= to internal /api/ URLs when access token is set', () => {
    setTokens({
      access_token: 'abc.def.ghi',
      refresh_token: 'r',
      token_type: 'bearer',
      expires_in: 60,
    });
    render(<Avatar photoUrl="/api/channels/7/photo" title="A" />);
    const img = screen.getByRole('presentation');
    expect(img.getAttribute('src')).toBe('/api/channels/7/photo?token=abc.def.ghi');
  });

  it('leaves internal URL unchanged when no token is in store', () => {
    render(<Avatar photoUrl="/api/channels/7/photo" title="A" />);
    const img = screen.getByRole('presentation');
    expect(img).toHaveAttribute('src', '/api/channels/7/photo');
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
