import Optlib.Autoformalization.Template.PGD_template

noncomputable section Lasso

class Lasso_pro (A b µ) where
  hA : A ≠ 0

def Lasso_pro.f (_ : Lasso_pro A b µ) : EuclideanSpace ℝ (Fin n) → ℝ :=
  fun x ↦ 1 / 2 * ‖A *ᵥ x - b‖ ^ 2 + µ * ‖x‖

instance Lasso_pg.pg (self : Lasso_pg pro x0) :
    pg (Lasso_pro.composite_pro pro) x0 where
  t := self.t
  x := self.x
  update := self.bad_update_lemma
  initial := self.initial

theorem Lasso_convergence
    (xm : EuclideanSpace ℝ (Fin n)) :
    ∀ k : ℕ, pro.target (alg.x k) - pro.target xm ≤ 1 / (k * alg.t) * ‖x0 - xm‖ ^ 2 := by
  sorry

end Lasso
