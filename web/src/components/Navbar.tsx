'use client'

import Link from 'next/link'
import Image from 'next/image'
import { useTranslations } from 'next-intl'
import { usePathname, useRouter } from 'next/navigation'
import { useState } from 'react'
import { authClient } from '@/lib/auth-client'
import type { User } from '@/lib/api'
import { LoginButton } from '@/components/LoginButton'
import { ThemeToggle } from '@/components/ThemeToggle'

interface NavbarProps { user: User | null; locale: string }

export function Navbar({ user, locale }: NavbarProps) {
  const t    = useTranslations('nav')
  const path = usePathname()
  const router = useRouter()
  const [mobileOpen, setMobileOpen] = useState(false)
  const base = `/${locale}`

  const isActive = (href: string) => path === `${base}${href}`

  const navLink = (href: string, label: string) => (
    <Link
      href={`${base}${href}`}
      onClick={() => setMobileOpen(false)}
      className={`text-sm font-medium transition-colors relative py-1 ${
        isActive(href)
          ? 'text-foreground'
          : 'text-muted-foreground hover:text-foreground'
      }`}
    >
      {label}
      {isActive(href) && (
        <span className="absolute -bottom-1 left-0 right-0 h-0.5 bg-primary rounded-full" />
      )}
    </Link>
  )

  const switchLocale = () => {
    const next = locale === 'fr' ? 'en' : 'fr'
    router.push(path.replace(`/${locale}`, `/${next}`))
  }

  const handleLogout = async () => {
    await authClient.signOut()
    router.refresh()
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/80 backdrop-blur-xl">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        {/* Logo */}
        <Link href={base} className="flex items-center gap-2.5 font-bold text-lg group">
          <span className="text-2xl group-hover:scale-110 transition-transform">🐾</span>
          <span className="gradient-hero font-extrabold tracking-tight">Hermes</span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-8">
          {navLink('', t('home'))}
          {navLink('/articles', t('articles'))}
          {navLink('/leaderboard', t('leaderboard'))}
          {user && navLink('/profile', t('profile'))}
          {user?.is_admin && navLink('/admin', t('admin'))}
        </nav>

        {/* Right section */}
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <button
            onClick={switchLocale}
            className="text-xs border border-border rounded-md px-2.5 py-1 text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-all"
          >
            {locale === 'fr' ? 'EN' : 'FR'}
          </button>

          {user ? (
            <div className="hidden md:flex items-center gap-3">
              {user.avatar ? (
                <Image src={user.avatar} alt={user.username} width={32} height={32}
                       className="rounded-full ring-2 ring-border" />
              ) : (
                <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center text-sm font-bold ring-2 ring-border">
                  {user.username[0]?.toUpperCase()}
                </div>
              )}
              <button
                onClick={handleLogout}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                {t('logout')}
              </button>
            </div>
          ) : (
            <LoginButton
              callbackURL={base}
              label={t('login')}
              className="hidden md:flex items-center gap-2 bg-discord text-white text-sm font-medium px-4 py-2 rounded-lg hover:opacity-90 transition-opacity"
              iconClassName="w-4 h-4"
            />
          )}

          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden p-2 text-muted-foreground hover:text-foreground"
            aria-label="Menu"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              {mobileOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden border-t border-border/40 bg-background/95 backdrop-blur-xl">
          <nav className="container mx-auto px-4 py-4 flex flex-col gap-4">
            {navLink('', t('home'))}
            {navLink('/articles', t('articles'))}
            {navLink('/leaderboard', t('leaderboard'))}
            {user && navLink('/profile', t('profile'))}
            {user?.is_admin && navLink('/admin', t('admin'))}
            <div className="border-t border-border/40 pt-4">
              {user ? (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {user.avatar ? (
                      <Image src={user.avatar} alt={user.username} width={28} height={28} className="rounded-full" />
                    ) : (
                      <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center text-xs font-bold">
                        {user.username[0]?.toUpperCase()}
                      </div>
                    )}
                    <span className="text-sm font-medium">{user.username}</span>
                  </div>
                  <button onClick={handleLogout} className="text-sm text-muted-foreground hover:text-foreground">
                    {t('logout')}
                  </button>
                </div>
              ) : (
                <LoginButton
                  callbackURL={base}
                  label={t('login')}
                  className="flex items-center justify-center gap-2 w-full bg-discord text-white text-sm font-medium px-4 py-2.5 rounded-lg hover:opacity-90 transition-opacity"
                  iconClassName="w-4 h-4"
                />
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  )
}
