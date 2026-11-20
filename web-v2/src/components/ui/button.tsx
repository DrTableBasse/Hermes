import Link from "next/link"
import { cva, type VariantProps } from "class-variance-authority"
import type { ComponentProps } from "react"
import { cn } from "@/lib/cn"

export const buttonVariants = cva(
  "relative inline-flex items-center justify-center gap-2 font-sans font-bold whitespace-nowrap transition-[transform,box-shadow,background-color] duration-200 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        // Violet de la maquette assombri pour l'AA sous le blanc ; curseur saucisse au survol.
        primary:
          "bg-linear-to-r from-violet-deep to-violet-deep-2 text-white shadow-[0_12px_32px_rgb(155_107_255/0.45)] hover:-translate-y-0.5 hover:shadow-[0_16px_40px_rgb(155_107_255/0.6)] hover:cursor-sausage",
        ghost:
          "border border-white/14 bg-white/6 font-semibold text-fg hover:bg-white/10",
        // Connexion avec Discord : couleur de la marque, à plat.
        discord: "bg-discord text-white hover:bg-[#4752C4]",
      },
      size: {
        sm: "rounded-[10px] px-3 py-[7px] text-[13px]",
        md: "rounded-xl px-[18px] py-2.5 text-sm",
        lg: "rounded-[14px] px-6 py-4 text-base",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
)

type Variants = VariantProps<typeof buttonVariants> & {
  /** Saucisse décorative posée sur le coin du bouton (bouton d'appel principal uniquement). */
  sausage?: boolean
}

type AsButton = Variants & ComponentProps<"button"> & { href?: undefined }
type AsLink = Variants & Omit<ComponentProps<typeof Link>, "href"> & { href: string }

function Sausage() {
  return (
    <svg
      className="absolute -top-4 -right-[18px] h-5 w-[54px] rotate-[18deg] transition-transform duration-350 ease-[cubic-bezier(.3,1.6,.5,1)] group-hover:translate-x-1 group-hover:-translate-y-2 group-hover:-rotate-[8deg]"
      viewBox="0 0 54 20"
      aria-hidden="true"
    >
      <rect x="1" y="1" width="52" height="18" rx="9" fill="#FF8A3D" stroke="#C25A1F" strokeWidth="2" />
      <path
        d="M14 6q3 4 0 8M26 6q3 4 0 8M38 6q3 4 0 8"
        stroke="#FFD2B0"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  )
}

/** Bouton ou lien stylé en bouton (lien dès que `href` est fourni). */
export function Button(props: AsButton | AsLink) {
  const { variant, size, sausage, className, children, ...rest } = props
  const classes = cn(buttonVariants({ variant, size }), sausage && "group", className)
  const content = (
    <>
      {children}
      {sausage && <Sausage />}
    </>
  )

  if (rest.href !== undefined) {
    const { href, ...linkProps } = rest as Omit<AsLink, keyof Variants | "className" | "children">
    const external = /^https?:\/\//.test(href)
    if (external) {
      return (
        <a href={href} className={classes} target="_blank" rel="noopener noreferrer" {...(linkProps as ComponentProps<"a">)}>
          {content}
        </a>
      )
    }
    return (
      <Link href={href} className={classes} {...linkProps}>
        {content}
      </Link>
    )
  }

  const buttonProps = rest as ComponentProps<"button">
  return (
    <button type="button" className={classes} {...buttonProps}>
      {content}
    </button>
  )
}
