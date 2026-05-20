import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  HomeIcon, BookmarkIcon, GridIcon, RefreshIcon,
  EyeIcon, EyeOffIcon, ShareIcon, SendIcon,
  TrashIcon, AlertCircleIcon,
} from '@/shared/ui/icons';

describe('icons', () => {
  it('all icons render as svg', () => {
    const icons = [
      HomeIcon, BookmarkIcon, GridIcon, RefreshIcon,
      EyeIcon, EyeOffIcon, ShareIcon, SendIcon,
      TrashIcon, AlertCircleIcon,
    ];
    for (const Icon of icons) {
      const { container, unmount } = render(<Icon />);
      expect(container.querySelector('svg')).not.toBeNull();
      unmount();
    }
  });

  it('applies size prop to width/height', () => {
    const { container } = render(<HomeIcon size={32} />);
    const svg = container.querySelector('svg')!;
    expect(svg.getAttribute('width')).toBe('32');
    expect(svg.getAttribute('height')).toBe('32');
  });

  it('passes className', () => {
    const { container } = render(<HomeIcon className="text-link" />);
    expect(container.querySelector('svg')).toHaveClass('text-link');
  });
});
