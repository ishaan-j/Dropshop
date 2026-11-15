export function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return <span className="block h-9 w-28" />;
  const width = 112;
  const height = 36;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const d = points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * width;
      const y = height - ((point - min) / span) * (height - 6) - 3;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  const down = points[points.length - 1] < points[0];
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-9 w-28" aria-hidden>
      <path d={d} fill="none" stroke={down ? "#146C3A" : "#8A938C"} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
