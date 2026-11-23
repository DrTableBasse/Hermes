import { Chip } from "@/components/ui/chip"

export type Grade = { name: string; slug: string; color: string }

/** Grade charcutier ; nom et couleur viennent de la table `grades` (aucune valeur en dur). */
export function GradeBadge({ grade, className }: { grade: Grade; className?: string }) {
  return (
    <Chip color={grade.color} data-grade={grade.slug} className={className}>
      {grade.name}
    </Chip>
  )
}
