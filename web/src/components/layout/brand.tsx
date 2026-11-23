import Link from "next/link"
import { cn } from "@/lib/cn"

/** Logo réservé (fourni plus tard par le propriétaire) + nom du serveur. */
export function Brand({ hideNameOnMobile = false }: { hideNameOnMobile?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-3 font-display text-xl font-bold">
      <span
        className="grid size-10 flex-none place-items-center rounded-[10px] border-[1.5px] border-dashed border-muted/60 font-sans text-[10px] font-medium text-muted"
        aria-hidden="true"
      >
        logo
      </span>
      <span className={cn(hideNameOnMobile && "max-[820px]:sr-only")}>SaucisseLand</span>
    </Link>
  )
}
