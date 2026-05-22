import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PostText } from '@/features/feed/PostText';

describe('PostText', () => {
  it('renders plain text when text_html is missing', () => {
    const { container } = render(
      <PostText text="hello world" textHtml={null} />,
    );
    expect(screen.getByText('hello world')).toBeInTheDocument();
    expect(container.querySelector('strong')).toBeNull();
  });

  it('renders text_html with HTML tags when provided', () => {
    const { container } = render(
      <PostText text="hello bold" textHtml="hello <strong>bold</strong>" />,
    );
    const strong = container.querySelector('strong');
    expect(strong).not.toBeNull();
    expect(strong?.textContent).toBe('bold');
  });

  it('renders nothing when both text and text_html are null', () => {
    const { container } = render(<PostText text={null} textHtml={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders clickable anchor for text_url-derived HTML', () => {
    render(
      <PostText
        text="click here"
        textHtml={
          'click <a href="https://example.com" rel="noopener noreferrer" target="_blank">here</a>'
        }
      />,
    );
    const link = screen.getByRole('link', { name: 'here' });
    expect(link).toHaveAttribute('href', 'https://example.com');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('renders mention with .tg-mention class', () => {
    const { container } = render(
      <PostText
        text="hi @alice"
        textHtml={
          'hi <a class="tg-mention" href="https://t.me/alice" rel="noopener noreferrer" target="_blank">@alice</a>'
        }
      />,
    );
    const mention = container.querySelector('a.tg-mention');
    expect(mention).not.toBeNull();
    expect(mention).toHaveAttribute('href', 'https://t.me/alice');
  });

  it('renders hashtag span with .tg-hashtag class', () => {
    const { container } = render(
      <PostText
        text="#trending"
        textHtml={'<span class="tg-hashtag">#trending</span>'}
      />,
    );
    const tag = container.querySelector('span.tg-hashtag');
    expect(tag).not.toBeNull();
    expect(tag?.textContent).toBe('#trending');
  });

  it('renders spoiler span with .tg-spoiler class', () => {
    const { container } = render(
      <PostText
        text="secret"
        textHtml={'<span class="tg-spoiler">secret</span>'}
      />,
    );
    expect(container.querySelector('span.tg-spoiler')).not.toBeNull();
  });

  it('reveals spoiler on click by adding .is-revealed', () => {
    const { container } = render(
      <PostText
        text="secret"
        textHtml={'<span class="tg-spoiler">secret</span>'}
      />,
    );
    const spoiler = container.querySelector('span.tg-spoiler');
    expect(spoiler?.classList.contains('is-revealed')).toBe(false);
    fireEvent.click(spoiler!);
    expect(spoiler?.classList.contains('is-revealed')).toBe(true);
  });

  it('preserves line breaks', () => {
    const { container } = render(
      <PostText text={'line 1\nline 2'} textHtml={null} />,
    );
    const div = container.querySelector('div');
    expect(div?.className).toContain('tf-cardtext');
    expect(div?.textContent).toBe('line 1\nline 2');
  });
});
