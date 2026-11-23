module
public import Mathlib.AlgebraicGeometry.Scheme
public import Mathlib.RingTheory.MvPowerSeries.Basic
@[expose] public section
noncomputable section
namespace ReciprocityTheory.ChartRestriction.G.Geo.Tor
open AlgebraicGeometry
abbrev Sp (R : Type) [CommRing R] : Scheme.{0} := Spec (CommRingCat.of R)
abbrev cpt (A : Type) [CommRing A] [IsLocalRing A] : Sp A := IsLocalRing.closedPoint A
namespace Germ
abbrev PS (R : Type) [CommRing R] (n d : ℕ) : Type := MvPowerSeries (Fin n × Fin d) R
abbrev Pt (R : Type) [CommRing R] (n d : ℕ) : Type := Fin d → PS R n d
end Germ
end ReciprocityTheory.ChartRestriction.G.Geo.Tor
namespace GlobalTheory.PlaceInt
open IsLocalRing ReciprocityTheory.ChartRestriction.G.Geo.Tor.Germ
variable {V : Type} [CommRing V] {d : ℕ}
def cpt {n : ℕ} (α : Fin d → V) : Pt V n d := fun i => MvPowerSeries.C (α i)
def Small [IsLocalRing V] (α : Fin d → V) : Prop := ∀ i, α i ∈ maximalIdeal V
end GlobalTheory.PlaceInt
end
