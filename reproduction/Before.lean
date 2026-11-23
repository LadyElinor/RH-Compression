import Contributions
noncomputable section
namespace GlobalTheory.SplitKernel
open IsLocalRing ReciprocityTheory.ChartRestriction.G.Geo.Tor
open ReciprocityTheory.ChartRestriction.G.Geo.Tor.Germ
open GlobalTheory.PlaceInt
theorem regression_constantCoeff_mem {V : Type} [CommRing V] [IsLocalRing V] {n d : ℕ} (α : Fin n → Fin d → V)
    (hα : (∀ b, Small (α b)) ∧ True) :
    ∀ b i, MvPowerSeries.constantCoeff ((fun j => cpt (n := 0) (α j)) b i) ∈ maximalIdeal V :=
  fun b i => by simpa [cpt] using hα.1 b i
end GlobalTheory.SplitKernel
end
