import Mathlib.LinearAlgebra.Matrix.NonsingularInverse

open Matrix
namespace GramRepair
variable {K : Type} [Field K] {n : ℕ}

theorem kernel_pairing (A : Matrix (Fin n) (Fin n) K) (c w : Fin n → K)
    (hc : c ᵥ* A = 0) : c ⬝ᵥ A *ᵥ w = 0 := by
  rw [Matrix.dotProduct_mulVec, hc, zero_dotProduct]

theorem inverse_pairing (A : Matrix (Fin n) (Fin n) K) (hd : A.det ≠ 0)
    (w : Fin n → K) (i : Fin n) : (Pi.single i 1 ᵥ* A⁻¹) ⬝ᵥ A *ᵥ w = w i := by
  rw [Matrix.dotProduct_mulVec, Matrix.vecMul_vecMul, Matrix.nonsing_inv_mul _ hd.isUnit, Matrix.vecMul_one, single_dotProduct, one_mul]

end GramRepair
