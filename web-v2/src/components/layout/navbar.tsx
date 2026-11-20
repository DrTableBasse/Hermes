"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { ChevronDown, LogOut, Menu, X } from "lucide-react"
import { useCallback, useEffect, useId, useRef, useState, useSyncExternalStore } from "react"
import { Avatar } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { glassClass } from "@/components/ui/glass"
import { Brand } from "@/components/layout/brand"
import { ACCOUNT_LINKS, MAIN_LINKS, isCurrent } from "@/components/layout/nav-links"
import { authClient } from "@/lib/auth-client"
import { cn } from "@/lib/cn"

type SessionUser = {
  name: string
  image?: string | null
  isAdmin?: boolean
  isRedacteur?: boolean
}

const sessionAtom = authClient.useSession
const noSession = () => null

/** Utilisateur connecté, `null` sinon (et pendant le rendu serveur). */
function useSessionUser(): SessionUser | null {
  const state = useSyncExternalStore(sessionAtom.listen, sessionAtom.get, noSession)
  return (state?.data?.user as SessionUser | undefined) ?? null
}

function useDismiss(open: boolean, close: () => void, ref: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close()
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close()
    }
    document.addEventListener("keydown", onKey)
    document.addEventListener("mousedown", onClick)
    return () => {
      document.removeEventListener("keydown", onKey)
      document.removeEventListener("mousedown", onClick)
    }
  }, [open, close, ref])
}

function accountLinksFor(user: SessionUser) {
  return ACCOUNT_LINKS.filter(l => !l.role || user[l.role])
}

function signIn(callbackURL: string) {
  void authClient.signIn.social({ provider: "discord", callbackURL })
}

function signOut() {
  void authClient.signOut()
}

function AccountMenu({ user }: { user: SessionUser }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const menuId = useId()
  const close = useCallback(() => setOpen(false), [])
  useDismiss(open, close, ref)

  return (
    <div ref={ref} className="relative max-[820px]:hidden">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 rounded-xl py-1 pr-2 pl-1 text-sm font-semibold hover:bg-white/6"
      >
        <Avatar name={user.name} src={user.image} size={32} />
        <span className="max-w-[14ch] truncate">{user.name}</span>
        <ChevronDown className={cn("size-4 text-muted transition-transform", open && "rotate-180")} aria-hidden="true" />
      </button>
      {open && (
        <div
          id={menuId}
          className="absolute top-[calc(100%+10px)] right-0 grid min-w-52 gap-0.5 rounded-2xl border border-white/10 bg-panel-2 p-2 shadow-[0_24px_50px_rgb(0_0_0/0.5)]"
        >
          {accountLinksFor(user).map(l => (
            <Link
              key={l.href}
              href={l.href}
              onClick={close}
              className="rounded-[10px] px-3 py-2 text-sm text-msg hover:bg-white/6 hover:text-fg"
            >
              {l.label}
            </Link>
          ))}
          <hr className="my-1 border-line" />
          <button
            type="button"
            onClick={signOut}
            className="flex items-center gap-2 rounded-[10px] px-3 py-2 text-left text-sm text-muted hover:bg-white/6 hover:text-fg"
          >
            <LogOut className="size-4" aria-hidden="true" />
            Se déconnecter
          </button>
        </div>
      )}
    </div>
  )
}

type NavbarProps = {
  /** `invite_url` des réglages publics ; `null` masque le bouton. */
  inviteUrl: string | null
}

export function Navbar({ inviteUrl }: NavbarProps) {
  const pathname = usePathname() ?? "/"
  const user = useSessionUser()
  const [mobileOpen, setMobileOpen] = useState(false)
  const mobileRef = useRef<HTMLDivElement>(null)
  const mobileId = useId()
  const closeMobile = useCallback(() => setMobileOpen(false), [])
  useDismiss(mobileOpen, closeMobile, mobileRef)

  return (
    <header className="sticky top-0 z-50 px-4 pt-4">
      <div ref={mobileRef} className="mx-auto max-w-[1360px]">
        <nav
          aria-label="Navigation principale"
          className={cn(glassClass.nav, "flex items-center justify-between gap-4 py-3 pr-3 pl-4")}
        >
          <Brand hideNameOnMobile />

          <ul className="flex gap-[34px] text-[15px] font-medium text-muted max-[820px]:hidden">
            {MAIN_LINKS.map(l => (
              <li key={l.href}>
                <Link
                  href={l.href}
                  aria-current={isCurrent(l.href, pathname) ? "page" : undefined}
                  className="transition-colors hover:text-fg aria-[current=page]:text-fg"
                >
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>

          <div className="flex items-center gap-2">
            {user ? (
              <AccountMenu user={user} />
            ) : (
              <button
                type="button"
                onClick={() => signIn(pathname)}
                className="rounded-xl px-3 py-2.5 text-sm font-semibold text-muted hover:text-fg max-[820px]:hidden"
              >
                Connexion
              </button>
            )}
            {inviteUrl && (
              <Button href={inviteUrl} size="md" className="shadow-none hover:shadow-none">
                Rejoindre Discord
              </Button>
            )}
            <button
              type="button"
              aria-expanded={mobileOpen}
              aria-controls={mobileId}
              aria-label={mobileOpen ? "Fermer le menu" : "Ouvrir le menu"}
              onClick={() => setMobileOpen(o => !o)}
              className="grid size-10 place-items-center rounded-xl border border-white/14 bg-white/6 min-[821px]:hidden"
            >
              {mobileOpen ? <X className="size-5" aria-hidden="true" /> : <Menu className="size-5" aria-hidden="true" />}
            </button>
          </div>
        </nav>

        {mobileOpen && (
          <div
            id={mobileId}
            className="mt-2 grid gap-1 rounded-[18px] border border-white/10 bg-panel-2 p-3 shadow-[0_24px_50px_rgb(0_0_0/0.5)] min-[821px]:hidden"
          >
            {MAIN_LINKS.map(l => (
              <Link
                key={l.href}
                href={l.href}
                onClick={closeMobile}
                aria-current={isCurrent(l.href, pathname) ? "page" : undefined}
                className="rounded-xl px-3 py-2.5 font-medium text-muted hover:bg-white/6 hover:text-fg aria-[current=page]:text-fg"
              >
                {l.label}
              </Link>
            ))}
            <hr className="my-1 border-line" />
            {user ? (
              <>
                <div className="flex items-center gap-3 px-3 py-2 text-sm font-semibold">
                  <Avatar name={user.name} src={user.image} size={28} />
                  {user.name}
                </div>
                {accountLinksFor(user).map(l => (
                  <Link
                    key={l.href}
                    href={l.href}
                    onClick={closeMobile}
                    className="rounded-xl px-3 py-2.5 text-sm text-msg hover:bg-white/6 hover:text-fg"
                  >
                    {l.label}
                  </Link>
                ))}
                <button
                  type="button"
                  onClick={signOut}
                  className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm text-muted hover:bg-white/6 hover:text-fg"
                >
                  <LogOut className="size-4" aria-hidden="true" />
                  Se déconnecter
                </button>
              </>
            ) : (
              <Button variant="discord" onClick={() => signIn(pathname)}>
                Se connecter avec Discord
              </Button>
            )}
          </div>
        )}
      </div>
    </header>
  )
}
