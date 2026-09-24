import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

// docs/specs/phase-09c-visual-redesign.md's Plan §10. Variant keys are the
// literal Status/Priority union values (api/types.ts) — no separate mapping
// table between a badge "kind" and a domain value.
const badgeVariants = cva(
  "inline-flex h-5 w-fit shrink-0 items-center justify-center rounded-sm border border-transparent px-2 py-0.5 text-xs font-medium uppercase text-white whitespace-nowrap",
  {
    variants: {
      variant: {
        open: "bg-status-open",
        in_progress: "bg-status-in_progress",
        resolved: "bg-status-resolved",
        rejected: "bg-status-rejected",
        high: "bg-priority-high",
        normal: "bg-priority-normal",
        low: "bg-priority-low",
      },
    },
    defaultVariants: {
      variant: "open",
    },
  }
)

function Badge({
  className,
  variant,
  asChild = false,
  ...props
}: React.ComponentProps<"span"> &
  Required<Pick<VariantProps<typeof badgeVariants>, "variant">> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "span"

  return (
    <Comp
      data-slot="badge"
      data-variant={variant}
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
