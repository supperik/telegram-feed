import { describe, expect, it, vi } from 'vitest';
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog';

describe('ConfirmDialog', () => {
  it('returns true when user confirms', () => {
    const spy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    expect(ConfirmDialog.confirm('Sure?')).toBe(true);
    expect(spy).toHaveBeenCalledWith('Sure?');
    spy.mockRestore();
  });

  it('returns false when user cancels', () => {
    const spy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    expect(ConfirmDialog.confirm('Sure?')).toBe(false);
    spy.mockRestore();
  });
});
