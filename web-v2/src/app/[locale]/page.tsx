import { getTranslations } from "next-intl/server"

export default async function HomePage() {
  const t = await getTranslations("Home")
  return (
    <main className="flex min-h-screen items-center justify-center">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
    </main>
  )
}
