"use client";

import * as SwitchPrimitive from "@radix-ui/react-switch";
import { useId } from "react";
import { cn } from "@/lib/utils";

export function Switch({
  checked,
  onCheckedChange,
  label,
  description,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
  description?: string;
}) {
  const id = useId();
  return (
    <div className="flex items-start justify-between gap-6 py-4">
      <div>
        <label htmlFor={id} className="text-sm font-medium text-[#17211C]">
          {label}
        </label>
        {description ? <p id={`${id}-hint`} className="mt-1 max-w-xl text-sm leading-6 text-[#5E6B63]">{description}</p> : null}
      </div>
      <SwitchPrimitive.Root
        id={id}
        checked={checked}
        onCheckedChange={onCheckedChange}
        aria-describedby={description ? `${id}-hint` : undefined}
        className={cn(
          "mt-0.5 h-6 w-11 shrink-0 rounded-full transition-colors",
          checked ? "bg-[#12372A]" : "bg-[#D7DBD0]",
        )}
      >
        <SwitchPrimitive.Thumb
          className={cn(
            "block h-5 w-5 rounded-full bg-white shadow-sm transition-transform",
            checked ? "translate-x-[22px]" : "translate-x-0.5",
          )}
        />
      </SwitchPrimitive.Root>
    </div>
  );
}
