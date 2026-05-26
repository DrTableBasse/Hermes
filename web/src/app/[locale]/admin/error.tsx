'use client'

import { useEffect } from 'react'

export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('[admin] page error:', error)
  }, [error])

  return (
    <div className="container mx-auto px-4 py-12 text-center">
      <p className="text-destructive font-medium mb-4">
        {error.message || 'Une erreur est survenue dans le panel admin.'}
      </p>
      <button
        onClick={reset}
        className="px-4 py-2 bg-secondary text-secondary-foreground rounded-lg text-sm hover:opacity-90"
      >
        Réessayer
      </button>
    </div>
  )
}
