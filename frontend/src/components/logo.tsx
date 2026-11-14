import { cn } from "@/lib/utils";

export function LogoMark({ className, inverted = false }: { className?: string; inverted?: boolean }) {
  const bag = inverted ? "#F7F8F2" : "#12372A";
  return (
    <svg viewBox="0 0 32 32" className={cn("h-8 w-8", className)} aria-hidden>
      <path d="M8.2 11.6h15.6l-1.25 13.2a2 2 0 0 1-2 1.8H11.45a2 2 0 0 1-2-1.8L8.2 11.6z" fill={bag} />
      <path d="M12.2 11.6V9.7a3.8 3.8 0 0 1 7.6 0v1.9" fill="none" stroke={bag} strokeWidth="1.7" strokeLinecap="round" />
      <path d="M16 15v6.4M13.3 18.6 16 21.4l2.7-2.8" fill="none" stroke="#C8F55A" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo({
  inverted = false,
  withWord = true,
  className,
}: {
  inverted?: boolean;
  withWord?: boolean;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LogoMark inverted={inverted} />
      {withWord ? (
        <span className={cn("text-lg font-semibold tracking-tight", inverted ? "text-[#F7F8F2]" : "text-[#12372A]")}>
          DropShop
        </span>
      ) : null}
    </span>
  );
}
