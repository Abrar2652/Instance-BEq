import Optlib.Autoformalization.Lemmas
import Optlib.Autoformalization.Template.GD_template

open Set Real Matrix Finset Filter Bornology BigOperators Topology Classical


noncomputable section Quadratic_minimization

local notation "‖" x "‖₂" => @Norm.norm _ (PiLp.instNorm 2 fun _ ↦ ℝ) x
local notation "‖" x "‖₁" => @Norm.norm _ (PiLp.instNorm 1 fun _ ↦ ℝ) x
local notation "|‖" A "|‖" => ‖(Matrix.toEuclideanLin ≪≫ₗ LinearMap.toContinuousLinearMap) A‖₊

class Quadratic_minimization_problem (Q : Matrix (Fin n) (Fin n) ℝ) (c : Fin n → ℝ) where
  hQ : Q ≠ 0
  hPd : PositiveDefinite Q

variable {Q : Matrix (Fin n) (Fin n) ℝ} {c : Fin n → ℝ}

def Quadratic_minimization_problem.f (_ : Quadratic_minimization_problem Q c) : EuclideanSpace ℝ (Fin n) → ℝ :=
  fun x ↦ 1 / 2 * ‖x - Q •ᵥ x - c‖₂ ^ 2

def Quadratic_minimization_problem.l (_ : Quadratic_minimization_problem Q c) : NNReal := |‖Qᵀ • Q|‖

instance Quadratic_minimization_problem.unconstrained_problem (self : Quadratic_minimization_problem Q c) :
    unconstrained_problem self.f where

variable {pro : Quadratic_minimization_problem Q c}

class Quadratic_minimization_GD (pro : Quadratic_minimization_problem Q c) (x₀ : EuclideanSpace ℝ (Fin n)) where
  t : ℝ
  x : ℕ → EuclideanSpace ℝ (Fin n)
  ht : t > 0
  update : ∀ k : ℕ,
    let gra : EuclideanSpace ℝ (Fin n) := Qᵀ •ᵥ (Q •ᵥ x k + c)
    x (k + 1) = x k - t • gra
  initial : x 0 = x₀

lemma Quadratic_minimization_problem.hasGradient (self : Quadratic_minimization_problem Q c) :
    ∀ x, HasGradientAt self.f (Qᵀ •ᵥ (Q •ᵥ x + c)) x := by
  unfold Quadratic_minimization_problem.f
  apply affine_sq_gradient

lemma Quadratic_minimization_problem.gradient_f (self : Quadratic_minimization_problem Q c) :
    ∀ x, gradient self.f x = Qᵀ •ᵥ (Q •ᵥ x + c) := by
  exact fun x ↦ HasGradientAt.gradient (self.hasGradient _)

lemma Quadratic_minimization_problem.pos_l (self : Quadratic_minimization_problem Q c) :
    self.l > 0 := by
  unfold Quadratic_minimization_problem.l; simp
  rw [Transpose_mul_self_eq_pos_definite]
  exact self.hPd

lemma Quadratic_minimization_GD.update_cor (self : Quadratic_minimization_GD pro x₀) :
    ∀ (k : ℕ), self.x (k + 1) = self.x k - self.t • gradient pro.f (self.x k) := by
  intro k
  rw [self.update k]
  rw [pro.gradient_f]

instance Quadratic_minimization_GD.Gradient_Descent (self : Quadratic_minimization_GD pro x₀) :
    Gradient_Descent (Quadratic_minimization_problem.unconstrained_problem pro) x₀ where
  x := self.x
  t := self.t
  l := pro.l
  update := self.update_cor
  hl := pro.pos_l
  step₁ := self.ht
  initial := self.initial

variable {alg : Quadratic_minimization_GD pro x₀}

lemma Quadratic_minimization_GD.diff (_ : Quadratic_minimization_GD pro x₀) :
    Differentiable ℝ pro.f := by
  exact (fun x ↦ HasGradientAt.differentiableAt (affine_sq_gradient Q c x))

lemma Quadratic_minimization_GD.smooth (_ : Quadratic_minimization_GD pro x₀) :
    LipschitzWith pro.l (gradient pro.f) := by
  rw [lipschitzWith_iff_norm_sub_le]; intro x y
  rw [pro.gradient_f, pro.gradient_f]
  rw [← Matrix.mulVec_sub, ← sub_add, sub_add_eq_add_sub, sub_add_cancel]
  rw [← Matrix.mulVec_sub]
  unfold Quadratic_minimization_problem.l
  simp
  apply Matrix.l2_opNorm_mulVec (Qᵀ • Q)

lemma Quadratic_minimization_GD.convex (_ : Quadratic_minimization_GD pro x₀) :
    ConvexOn ℝ Set.univ pro.f := by
  unfold Quadratic_minimization_problem.f
  exact affine_sq_convex Q c

lemma Quadratic_minimization_GD.point_descent
    (step₂ : alg.t ≤ 1 / pro.l) (xm : EuclideanSpace ℝ (Fin n)) :
    ∀ k : ℕ, pro.f (alg.x (k + 1)) ≤ pro.f xm + 1 / ((2 : ℝ) * alg.t)
      * (‖alg.x k - xm‖ ^ 2 - ‖alg.x (k + 1) - xm‖ ^ 2) := by
  apply point_descent_for_convex (alg := alg.Gradient_Descent) alg.diff alg.smooth alg.convex step₂ xm

-- the O(1/t) descent property of the gradient method
lemma Quadratic_minimization_GD.gradient_method
    (step₂ : alg.t ≤ 1 / pro.l) (xm : EuclideanSpace ℝ (Fin n)) :
    ∀ k : ℕ, pro.f (alg.x (k + 1)) - pro.f xm ≤ 1 / (2 * (k + 1) * alg.t) * ‖x₀ - xm‖ ^ 2 := by
  apply gradient_method_convergence (alg := alg.Gradient_Descent) alg.diff alg.smooth alg.convex step₂ xm

end Quadratic_minimization
