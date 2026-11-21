import { LegalPage, legalMetadata } from "@/components/legal/legal-page"

export const generateMetadata = () => legalMetadata("mentions-legales")

export default function Page() {
  return <LegalPage slug="mentions-legales" />
}
