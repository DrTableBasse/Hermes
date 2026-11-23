import { LegalPage, legalMetadata } from "@/components/legal/legal-page"

export const generateMetadata = () => legalMetadata("reglement")

export default function Page() {
  return <LegalPage slug="reglement" />
}
