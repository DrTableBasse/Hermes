import type { Metadata } from "next"
import { Button } from "@/components/ui/button"

export const metadata: Metadata = {
  title: "Page introuvable · SaucisseLand",
  robots: { index: false, follow: false },
}

export default function NotFound() {
  return (
    <main className="relative pt-10 pb-24">
      <div className="relative mx-auto max-w-[760px] px-6">
        <p className="m-0 font-display text-[clamp(64px,12vw,120px)] leading-none font-extrabold tracking-[-0.04em] text-violet">404</p>
        <h1 className="my-4 font-display text-[clamp(28px,4vw,44px)] leading-[1.05] font-extrabold tracking-[-0.03em] text-balance">
          Hermes a cherché partout. Même sous le grill.
        </h1>
        <p className="mt-0 mb-8 max-w-[56ch] text-lg text-muted">
          Cette page n’existe pas, ou plus. Elle a peut-être été promue ailleurs sans qu’on nous prévienne.
        </p>
        <Button href="/" size="lg">
          Retour à l’accueil
        </Button>
      </div>
    </main>
  )
}
