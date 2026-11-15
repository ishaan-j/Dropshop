import type { ProductArt } from "@/types";
import { cn } from "@/lib/utils";

export function ProductArt({
  art,
  label,
  className,
}: {
  art: ProductArt;
  label: string;
  className?: string;
}) {
  return (
    <div role="img" aria-label={label} className={cn("overflow-hidden bg-[#EEF2E6]", className)}>
      <svg viewBox="0 0 160 160" className="h-full w-full">
        <circle cx="80" cy="86" r="48" fill="#E3EBD6" />
        <ArtShape art={art} />
      </svg>
    </div>
  );
}

function ArtShape({ art }: { art: ProductArt }) {
  switch (art) {
    case "nike":
    case "samba":
    case "runner":
      return (
        <g fill="none" stroke="#12372A" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <path d="M38 102c18-18 28-28 46-28 14 0 22 8 34 8 10 0 16-4 22-8" />
          <path d="M42 102h78c6 0 10 6 8 12l-4 8H50c-8 0-14-6-8-20z" fill="#12372A" stroke="none" />
          <path d="M58 108h46" stroke="#C8F55A" strokeWidth="3" />
          {art === "samba" ? <path d="M62 96h18M66 90h14" /> : null}
        </g>
      );
    case "headphones":
      return (
        <g fill="#12372A">
          <path d="M48 78v18a14 14 0 0 0 14 14h2V70H62a14 14 0 0 0-14 8z" />
          <path d="M96 70h2a14 14 0 0 1 14 14v12a14 14 0 0 1-14 14h-2V70z" />
          <path d="M54 74c2-20 12-32 26-32s24 12 26 32" fill="none" stroke="#12372A" strokeWidth="6" />
          <rect x="50" y="92" width="10" height="16" rx="2" fill="#C8F55A" />
        </g>
      );
    case "airpods":
      return (
        <g fill="#12372A">
          <rect x="58" y="78" width="44" height="36" rx="10" />
          <rect x="66" y="86" width="28" height="8" rx="3" fill="#C8F55A" />
          <rect x="46" y="46" width="16" height="34" rx="8" />
          <rect x="98" y="46" width="16" height="34" rx="8" />
        </g>
      );
    case "dyson":
      return (
        <g fill="#12372A">
          <rect x="72" y="36" width="16" height="78" rx="8" />
          <circle cx="80" cy="40" r="12" fill="#C8F55A" />
          <path d="M72 96c-16 8-22 18-22 28h60c0-10-6-20-22-28z" />
        </g>
      );
    case "leggings":
      return (
        <g fill="#12372A">
          <path d="M58 42h44l-4 76H86l-6-34-6 34H62L58 42z" />
          <path d="M64 54h32" stroke="#C8F55A" strokeWidth="3" />
        </g>
      );
    case "kindle":
      return (
        <g>
          <rect x="48" y="36" width="64" height="88" rx="6" fill="#12372A" />
          <rect x="56" y="46" width="48" height="60" rx="2" fill="#F7F8F2" />
          <circle cx="80" cy="114" r="3" fill="#C8F55A" />
        </g>
      );
    case "fryer":
      return (
        <g fill="#12372A">
          <rect x="46" y="48" width="68" height="64" rx="12" />
          <rect x="58" y="40" width="44" height="14" rx="4" fill="#C8F55A" />
          <rect x="60" y="68" width="40" height="24" rx="4" fill="#F7F8F2" />
        </g>
      );
    case "jacket":
      return (
        <g fill="#12372A">
          <path d="M60 48 80 38l20 10 14 18v52H46V66z" />
          <path d="M80 38v70" stroke="#C8F55A" strokeWidth="3" />
        </g>
      );
    case "espresso":
      return (
        <g fill="#12372A">
          <rect x="46" y="50" width="68" height="52" rx="6" />
          <rect x="58" y="40" width="28" height="12" rx="2" />
          <path d="M46 78h-12c0 12 6 16 12 16" fill="none" stroke="#12372A" strokeWidth="4" />
          <rect x="64" y="108" width="32" height="8" rx="2" fill="#C8F55A" />
        </g>
      );
    case "shirt":
      return (
        <g fill="#12372A">
          <path d="M58 50 80 40l22 10 16 12-14 10-8-8v46H64V64l-8 8-14-10z" />
          <path d="M80 40v28" stroke="#C8F55A" strokeWidth="3" />
        </g>
      );
    default:
      return (
        <g>
          <path d="M52 62h56l-4 48H56z" fill="#12372A" />
          <path d="M64 62v-6a16 16 0 0 1 32 0v6" fill="none" stroke="#12372A" strokeWidth="4" />
          <path d="M80 78v22M72 92l8 8 8-8" fill="none" stroke="#C8F55A" strokeWidth="3" strokeLinecap="round" />
        </g>
      );
  }
}
