import HermForms

noncomputable section
open NumberField ReciprocityTheory.ChartRestriction.G.FD
open GlobalTheory.IndefiniteRowSideFullHecke.AdmissibleHarmonicLattice

theorem witness_iff_integral {E : Type} [Field E] [NumberField E] [IsCMField E]
    {n : ℕ} (x y : Fin n → E) :
    (∃ a : 𝓞 E, (a : E) = stdForm x y) ↔ IsIntegral ℤ (herm 1 x y) := by
  rw [GlobalTheory.SW.Base.herm_one]
  exact ⟨fun ⟨a, ha⟩ => ha ▸ a.isIntegral_coe, fun h => ⟨⟨_, h⟩, rfl⟩⟩
end
