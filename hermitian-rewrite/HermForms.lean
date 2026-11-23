module
public import Mathlib.NumberTheory.NumberField.CMField
public import Mathlib.Data.Matrix.Basic

@[expose] public section
noncomputable section
open NumberField
variable {E : Type} [Field E] [NumberField E] [IsCMField E] {n : ℕ}

namespace ReciprocityTheory.ChartRestriction.G.FD

def cc (z : E) : E := IsCMField.complexConj E z

def herm (G : Matrix (Fin n) (Fin n) E) (x y : Fin n → E) : E :=
  ∑ i, ∑ j, x i * G i j * cc (y j)
end ReciprocityTheory.ChartRestriction.G.FD

namespace GlobalTheory.IndefiniteRowSideFullHecke.AdmissibleHarmonicLattice

def stdForm (x y : Fin n → E) : E := ∑ i, x i * IsCMField.complexConj E (y i)
end GlobalTheory.IndefiniteRowSideFullHecke.AdmissibleHarmonicLattice

open ReciprocityTheory.ChartRestriction.G.FD
open GlobalTheory.IndefiniteRowSideFullHecke.AdmissibleHarmonicLattice

namespace GlobalTheory.SW.Base

theorem herm_one (x y : Fin n → E) : herm 1 x y = ∑ i, x i * cc (y i) := by
  unfold herm
  refine Finset.sum_congr rfl fun i _ => ?_
  rw [Finset.sum_eq_single i] <;> simp +contextual [eq_comm]
end GlobalTheory.SW.Base

namespace GlobalTheory.GenusSelfDual

theorem herm_one (x y : Fin n → E) : herm 1 x y = stdForm x y :=
  GlobalTheory.SW.Base.herm_one x y
end GlobalTheory.GenusSelfDual

end
