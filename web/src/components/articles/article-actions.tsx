"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState } from "react"
import { api } from "@/lib/api/client"
import { seg } from "@/lib/api/query"

/** Modifier / supprimer un article, pour son auteur et les administrateurs. */
export function ArticleActions({ articleId }: { articleId: number }) {
  const router = useRouter()
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState("")

  async function remove() {
    if (!window.confirm("Supprimer cet article définitivement ?")) return
    setDeleting(true)
    setError("")
    try {
      await api.articles.delete(articleId)
      router.push("/articles")
      router.refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur inattendue")
      setDeleting(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <Link
        href={`/editeur/${seg(articleId)}`}
        prefetch={false}
        className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted hover:border-violet/40 hover:text-fg"
      >
        Modifier
      </Link>
      <button
        type="button"
        onClick={remove}
        disabled={deleting}
        className="rounded-lg border border-[#FF8F8F]/50 px-3 py-1.5 text-sm text-[#FF8F8F] hover:bg-[#FF8F8F]/10 disabled:opacity-50"
      >
        {deleting ? "…" : "Supprimer"}
      </button>
      {error && (
        <span role="alert" className="text-xs text-[#FF8F8F]">
          {error}
        </span>
      )}
    </div>
  )
}
