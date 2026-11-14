"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({
  className,
  children,
  full = false,
  hideClose = false,
}: {
  className?: string;
  children: ReactNode;
  full?: boolean;
  hideClose?: boolean;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[#17211C]/40" />
      <DialogPrimitive.Content
        className={cn(
          "fixed z-50 bg-white focus:outline-none",
          full
            ? "inset-0 flex h-full w-full flex-col"
            : "left-1/2 top-1/2 max-h-[min(90vh,840px)] w-[min(100%-1.5rem,40rem)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl border border-[#E4E7DC] p-6 shadow-[0_24px_60px_rgba(18,55,42,0.16)]",
          className,
        )}
      >
        {children}
        {!hideClose && !full ? (
          <DialogPrimitive.Close className="absolute right-4 top-4 rounded-md p-1 text-[#5E6B63] hover:bg-[#F3F5EE] hover:text-[#17211C]" aria-label="Close">
            <X className="h-4 w-4" />
          </DialogPrimitive.Close>
        ) : null}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export function DialogTitle({ className, ...props }: DialogPrimitive.DialogTitleProps) {
  return <DialogPrimitive.Title className={cn("text-lg font-semibold tracking-tight text-[#12372A]", className)} {...props} />;
}

export function DialogDescription({ className, ...props }: DialogPrimitive.DialogDescriptionProps) {
  return <DialogPrimitive.Description className={cn("mt-2 text-sm leading-6 text-[#5E6B63]", className)} {...props} />;
}
