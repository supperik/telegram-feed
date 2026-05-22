import type { ReactNode, SVGProps } from 'react';

interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'width' | 'height'> {
  size?: number;
}

interface IconOpts {
  viewBox?: string;
  dataIcon?: string;
  filled?: boolean;
}

// Lucide-style line icons from the redesign — 1.75 stroke, 24×24, currentColor.
function makeIcon(path: ReactNode, opts: IconOpts = {}) {
  const { viewBox = '0 0 24 24', dataIcon, filled = false } = opts;
  return function Icon({ size = 24, className, ...rest }: IconProps) {
    return (
      <svg
        width={size}
        height={size}
        viewBox={viewBox}
        fill={filled ? 'currentColor' : 'none'}
        stroke={filled ? 'none' : 'currentColor'}
        strokeWidth={filled ? 0 : 1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
        aria-hidden="true"
        data-icon={dataIcon}
        {...rest}
      >
        {path}
      </svg>
    );
  };
}

export const HomeIcon = makeIcon(
  <>
    <path d="M3 11.5 12 4l9 7.5" />
    <path d="M5.5 10.5V20h13v-9.5" />
    <path d="M10 20v-5h4v5" />
  </>,
);
export const BookmarkIcon = makeIcon(<path d="M6 3h12v18l-6-4.5L6 21V3z" />);
export const BookmarkFillIcon = makeIcon(<path d="M6 3h12v18l-6-4.5L6 21V3z" />, { filled: true });
export const GridIcon = makeIcon(
  <>
    <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
    <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" />
    <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" />
    <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" />
  </>,
);
export const RefreshIcon = makeIcon(
  <>
    <path d="M3 12a9 9 0 0 1 15.5-6.2L21 8" />
    <path d="M21 3v5h-5" />
    <path d="M21 12a9 9 0 0 1-15.5 6.2L3 16" />
    <path d="M3 21v-5h5" />
  </>,
);
export const EyeIcon = makeIcon(
  <>
    <path d="M2.5 12C4 9.5 7.5 6 12 6s8 3.5 9.5 6c-1.5 2.5-5 6-9.5 6s-8-3.5-9.5-6z" />
    <circle cx="12" cy="12" r="3" />
  </>,
);
export const EyeOffIcon = makeIcon(
  <>
    <path d="M3 3 21 21" />
    <path d="M10.6 6.1A9.7 9.7 0 0 1 12 6c4.5 0 8 3.5 9.5 6-.5.8-1.2 1.7-2.1 2.6" />
    <path d="M16.5 16.5A9.5 9.5 0 0 1 12 18c-4.5 0-8-3.5-9.5-6 .8-1.4 1.9-2.7 3.3-3.7" />
    <path d="M10 10a3 3 0 1 0 4 4" />
  </>,
);
export const TrashIcon = makeIcon(
  <>
    <path d="M4 7h16" />
    <path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />
    <path d="M6 7v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7" />
    <path d="M10 11v6" />
    <path d="M14 11v6" />
  </>,
);
export const LockIcon = makeIcon(
  <>
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V8a4 4 0 0 1 8 0v3" />
  </>,
  { dataIcon: 'lock' },
);
export const SendIcon = makeIcon(<path d="M3.5 12 21 4l-7 17-3-7-7-2z" />);
export const ShareIcon = makeIcon(
  <>
    <polyline points="15 17 20 12 15 7" />
    <path d="M4 18v-2a4 4 0 0 1 4-4h12" />
  </>,
);
export const ArrowUpRightIcon = makeIcon(
  <>
    <path d="M7 17 17 7" />
    <path d="M9 7h8v8" />
  </>,
);
export const PlusIcon = makeIcon(
  <>
    <path d="M12 5v14" />
    <path d="M5 12h14" />
  </>,
);
export const CheckIcon = makeIcon(<path d="M5 12.5 10 17.5 19 7.5" />);
export const ChevronLeftIcon = makeIcon(<path d="M14 6l-6 6 6 6" />);
export const ChevronRightIcon = makeIcon(<path d="M9 18l6-6-6-6" />);
export const ChevronDownIcon = makeIcon(<path d="M6 9l6 6 6-6" />);
export const AlertCircleIcon = makeIcon(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v4.5" />
    <path d="M12 16.5v.01" />
  </>,
);
export const PlayIcon = makeIcon(<path d="M7 5v14l12-7-12-7z" />, { filled: true });
export const FileIcon = makeIcon(
  <>
    <path d="M7 3h8l4 4v14H7z" />
    <path d="M14 3v5h5" />
  </>,
);
export const LoaderIcon = makeIcon(
  <>
    <path d="M12 3v3" />
    <path d="M12 18v3" />
    <path d="M5.6 5.6l2.1 2.1" />
    <path d="M16.3 16.3l2.1 2.1" />
    <path d="M3 12h3" />
    <path d="M18 12h3" />
    <path d="M5.6 18.4l2.1-2.1" />
    <path d="M16.3 7.7l2.1-2.1" />
  </>,
);
export const UsersIcon = makeIcon(
  <>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
    <path d="M16 8.5a3 3 0 0 1 0 6" />
    <path d="M17.5 20a5.5 5.5 0 0 0-3-4.9" />
  </>,
);
export const ClockIcon = makeIcon(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </>,
);
