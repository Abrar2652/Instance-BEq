import Optlib.Autoformalization.Template.GD_template

noncomputable section LeastSquares

local notation "‖" x "‖₂" => @Norm.norm _ (PiLp.instNorm 2 fun _ ↦ ℝ) x

class LeastSquares_problem {m n : ℕ} (A : Matrix (Fin m) (Fin n) ℝ) (b : Fin m → ℝ) where
  hA : A ≠ 0

def LeastSquares_problem.f (_ : LeastSquares_problem A b) : EuclideanSpace ℝ (Fin n) → ℝ :=
  fun x ↦ 1 / 2 * ‖A *ᵥ x - b‖₂ ^ 2

instance LeastSquares_GD.Gradient_Descent (self : LeastSquares_GD pro x₀) :
    Gradient_Descent (LeastSquares_problem.unconstrained_problem pro) x₀ where
  x := self.x
  t := self.t
  l := pro.l
  update := self.update_cor
  hl := pro.pos_l
  step₁ := self.ht
  initial := self.initial

lemma LeastSquares_GD.gradient_method
    (step₂ : alg.t ≤ 1 / pro.l) (xm : EuclideanSpace ℝ (Fin n)) :
    ∀ k : ℕ, pro.f (alg.x (k + 1)) - pro.f xm ≤ 1 / (2 * (k + 1) * alg.t) * ‖x₀ - xm‖ ^ 2 := by
  apply gradient_method_convergence (alg := alg.Gradient_Descent) alg.diff alg.smooth alg.convex step₂ xm

end LeastSquares
