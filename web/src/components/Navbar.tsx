'use client'

import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { usePathname, useRouter } from 'next/navigation'
import { useState } from 'react'
import type { User } from '@/lib/api'

interface NavbarProps { user: User | null; locale: string }

export function Navbar({ user, locale }: NavbarProps) {
  const t    = useTranslations('nav')
  const path = usePathname()
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const base = `/${locale}`

  const navLink = (href: string, label: string) => (
    <Link
      href={`${base}${href}`}
      className={`text-sm font-medium transition-colors hover:text-primary ${
        path === `${base}${href}` ? 'text-primary' : 'text-muted-foreground'
      }`}
    >
      {label}
    </Link>
  )

  const switchLocale = () => {
    const next = locale === 'fr' ? 'en' : 'fr'
    router.push(path.replace(`/${locale}`, `/${next}`))
  }

  const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur">
      <div className="container mx-auto flex h-14 items-center justify-between px-4">
        <Link href={base} className="flex items-center gap-2 font-bold text-lg">
          <span className="text-2xl">🐾</span> Hermes
        </Link>

        <nav className="hidden md:flex items-center gap-6">
          {navLink('', t('home'))}
          {navLink('/articles', t('articles'))}
          {navLink('/leaderboard', t('leaderboard'))}
          {user && navLink('/profile', t('profile'))}
          {user?.is_admin && navLink('/admin', t('admin'))}
        </nav>

        <div className="flex items-center gap-3">
          <button
            onClick={switchLocale}
            className="text-xs border border-border rounded px-2 py-1 text-muted-foreground hover:text-foreground transition-colors"
          >
            {locale === 'fr' ? 'EN' : 'FR'}
          </button>

          {user ? (
            <div className="flex items-center gap-2">
              {user.avatar ? (
                <img src={user.avatar} alt={user.username} className="w-8 h-8 rounded-full" />
              ) : (
                <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center text-sm font-bold">
                  {user.username[0]?.toUpperCase()}
                </div>
              )}
              <form action={`${API}/auth/logout`} method="POST">
                <button type="submit" className="text-sm text-muted-foreground hover:text-foreground">
                  {t('logout')}
                </button>
              </form>
            </div>
          ) : (
            <a
              href={`${API}/auth/login`}
              className="flex items-center gap-2 bg-[#5865F2] text-white text-sm font-medium px-3 py-1.5 rounded-md hover:bg-[#4752C4] transition-colors"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z"/>
              </svg>
              {t('login')}
            </a>
          )}
        </div>
      </div>
    </header>
  )
}
