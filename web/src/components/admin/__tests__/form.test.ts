import { describe, expect, it } from "vitest"
import { ApiError } from "@/lib/api/client"
import { adminErrorText } from "@/components/admin/form"

describe("adminErrorText", () => {
  it("403 avec détail de l’API : texte exact renvoyé", () => {
    expect(adminErrorText(new ApiError(403, "Droit requis : Sanctionner"))).toBe("Droit requis : Sanctionner")
  })

  it("403 sans détail (statusText ou repli) : message générique", () => {
    expect(adminErrorText(new ApiError(403, "Forbidden"))).toBe("Action réservée à l’administration.")
    expect(adminErrorText(new ApiError(403, "Erreur API"))).toBe("Action réservée à l’administration.")
    expect(adminErrorText(new ApiError(403, ""))).toBe("Action réservée à l’administration.")
  })
})
