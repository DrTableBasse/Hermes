'use server'

import { headers } from 'next/headers'
import { auth } from '@/lib/auth'

const WEB_API = process.env.WEB_API_INTERNAL_URL ?? 'http://web-api:8000'

async function apiFetch(path: string, method: string, body?: unknown) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) throw new Error('Non authentifié')
  const token = (session.session as any).token as string

  const res = await fetch(`${WEB_API}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      Cookie: `better-auth.session_token=${token}`,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: 'no-store',
  })

  if (res.status === 204) return null
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail ?? `Erreur ${res.status}`)
  return data
}

export async function actionCreateArticle(payload: {
  title: string
  content: string
  cover_image_url?: string
  published: boolean
  tag_ids: number[]
}) {
  return apiFetch('/articles', 'POST', payload)
}

export async function actionUpdateArticle(id: number, payload: {
  title?: string
  content?: string
  cover_image_url?: string
  published?: boolean
  tag_ids?: number[]
}) {
  return apiFetch(`/articles/${id}`, 'PUT', payload)
}

export async function actionDeleteArticle(id: number) {
  return apiFetch(`/articles/${id}`, 'DELETE')
}

export async function actionCreateTag(payload: { name: string; color: string }) {
  return apiFetch('/tags', 'POST', payload)
}

export async function actionUpdateTag(id: number, payload: { name?: string; color?: string }) {
  return apiFetch(`/tags/${id}`, 'PUT', payload)
}

export async function actionDeleteTag(id: number) {
  return apiFetch(`/tags/${id}`, 'DELETE')
}

export async function actionUploadMedia(formData: FormData) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) throw new Error('Non authentifié')
  const token = (session.session as any).token as string

  const res = await fetch(`${WEB_API}/media/upload`, {
    method: 'POST',
    headers: { Cookie: `better-auth.session_token=${token}` },
    body: formData,
    cache: 'no-store',
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail ?? `Erreur ${res.status}`)
  return data as { url: string; filename: string }
}
