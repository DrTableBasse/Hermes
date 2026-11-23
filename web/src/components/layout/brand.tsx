import Image from "next/image"
import Link from "next/link"
import logo from "@/assets/logo.png"
import { cn } from "@/lib/cn"

/** Logo du serveur Discord (teckel) + nom du serveur. */
export function Brand({ hideNameOnMobile = false }: { hideNameOnMobile?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-3 font-display text-xl font-bold">
      <Image
        src={logo}
        alt=""
        width={40}
        height={40}
        priority
        className="size-10 flex-none rounded-full bg-white ring-[1.5px] ring-violet/70"
      />
      <span className={cn(hideNameOnMobile && "max-[820px]:sr-only")}>SaucisseLand</span>
    </Link>
  )
}
