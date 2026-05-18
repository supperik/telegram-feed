interface Props {
  photoUrl: string | null;
  title: string;
  size?: number;
}

const GRADIENTS = [
  'linear-gradient(135deg, #5fa8ff, #2778d6)',
  'linear-gradient(135deg, #ff8a65, #e64a19)',
  'linear-gradient(135deg, #81c784, #2e7d32)',
  'linear-gradient(135deg, #ba68c8, #6a1b9a)',
  'linear-gradient(135deg, #ffb74d, #ef6c00)',
  'linear-gradient(135deg, #4dd0e1, #00838f)',
];

function gradientFor(title: string): string {
  let hash = 0;
  for (let i = 0; i < title.length; i++) hash = (hash * 31 + title.charCodeAt(i)) | 0;
  return GRADIENTS[Math.abs(hash) % GRADIENTS.length];
}

export function Avatar({ photoUrl, title, size = 44 }: Props) {
  const initial = title.trim()[0]?.toUpperCase() ?? '?';
  const style = { width: `${size}px`, height: `${size}px` };
  if (photoUrl) {
    return (
      <img
        src={photoUrl}
        alt=""
        style={style}
        className="shrink-0 rounded-full object-cover"
      />
    );
  }
  return (
    <div
      style={{ ...style, background: gradientFor(title) }}
      className="flex shrink-0 items-center justify-center rounded-full font-semibold text-white"
    >
      <span style={{ fontSize: `${Math.round(size * 0.42)}px` }}>{initial}</span>
    </div>
  );
}
