import Optlib.Autoformalization.Lemmas
import Optlib.Autoformalization.Template.GD_template

open Set Real Matrix Finset Filter Bornology BigOperators Topology Classical


noncomputable section Ridge_regression

local notation "‖" x "‖₂" => @Norm.norm _ (PiLp.instNorm 2 fun _ ↦ ℝ) x
local notation "‖" x "‖₁" => @Norm.norm _ (PiLp.instNorm 1 fun _ ↦ ℝ) x
user

Continue from where you left off:

```lean
local notation "‖" x "‖₁" => @Norm.norm _ (PiLp.instNorm 1 fun _ ↦ ℝ) x
local notation "|‖" A "|‖" => ‖(Matrix.toEuclideanLin ≪≫ₗ LinearMap.toContinuousLinearMap) A‖₊

class Ridge_regression_problem {m n : ℕ} (A : Matrix (Fin m) (Fin n) ℝ) (b : Fin m → ℝ) (lam_ : ℝ) where
  hA : A ≠ 0

variable {A : Matrix (Fin m) (Fin n) ℝ} {b : Fin m → ℝ} {lam_ : ℝ}

def Ridge_regression_problem.f (_ : Ridge_regression_problem A b lam_) : EuclideanSpace ℝ (Fin n) → ℝ :=
  fun x ↦ 1 / 2 * ‖A *ᵥ x - b‖₂ ^ 2 + lam_ / 2 * ‖x‖₂ ^ 2

def Ridge_regression_problem.l (_ : Ridge_regression_problem A b lam_) : NNReal := |‖Aᵀ * A + lam_ * I n|‖

instance Ridge_regression_problem.unconstrained_problem (self : Ridge_regression_problem A b lam_) :
    unconstrained_problem self.f where

variable {pro : Ridge_regression_problem A b lam_}

class Ridge_regression_GD (pro : Ridge_regression_problem A b lam_) (x₀ : EuclideanSpace ℝ (Fin n)) where
  t : ℝ
  x : ℕ → EuclideanSpace ℝ (Fin n)
  ht : t > 0
  update : ∀ k : ℕ,
    let gra : EuclideanSpace ℝ (Fin n) := Aᵀ *ᵥ (A *ᵥ x k - b) + lam_ • x k
    x (k + 1) = x k - t • gra
  initial : x 0 = x₀

lemma Ridge_regression_problem.hasGradient (self : Ridge_regression_problem A b lam_) :
    ∀ x, HasGradientAt self.f (Aᵀ *ᵥ (A *ᵥ x - b) + lam_ • x) x := by
  unfold Ridge_regression_problem.f
  apply affine_sq_gradient

lemma Ridge_regression_problem.gradient_f (self : Ridge_regression_problem A b lam_) :
    ∀ x, gradient self.f x = Aᵀ *ᵥ (A *ᵥ x - b) + lam_ • x := by
  exact fun x ↦ HasGradientAt.gradient (self.hasGradient _)

lemma Ridge_regression_problem.pos_l (self : Ridge_regression_problem A b lam_) :
    self.l > 0 := by
  unfold Ridge_regression_problem.l
  simp
  rw [Transpose_mul_self_eq_zero, smul_one]
  exact self.hA

lemma Ridge_regression_GD.update_cor (self : Ridge_regression_GD pro x₀) :
    ∀ (k : ℕ), self.x (k + 1) = self.x k - self.t • gradient pro.f (self.x k) := by
  intro k
  rw [self.update k]
  rw [pro.gradient_f]

instance Ridge_regression_GD.Gradient_Descent (self : Ridge_regression_GD pro x₀) :
    Gradient_Descent (Ridge_regression_problem.unconstrained_problem pro) x₀ where
  x := self.x
  t := self.t
  l := pro.l
  update := self.update_cor
  hl := pro.pos_l
  step₁ := self.ht
  initial := self.initial

variable {alg : Ridge_regression_GD pro x₀}

lemma Ridge_regression_GD.diff (_ : Ridge_regression_GD pro x₀) :
    Differentiable ℝ pro.f := by
  exact (fun x ↦ HasGradientAt.differentiableAt (affine_sq_gradient A b lam_ x))

lemma Ridge_regression_GD.smooth (_ : Ridge_regression_GD pro x₀) :
    LipschitzWith pro.l (gradient pro.f) := by
  rw [lipschitzWith_iff_norm_sub_le]; intro x y
  rw [pro.gradient_f, pro.gradient_f]
  rw [← Matrix.mulVec_sub, ← sub_add, sub_add_eq_add_sub, sub_add_cancel]
  rw [← Matrix.mulVec_sub]
  unfold Ridge_regression_problem.l
  simp
  apply Matrix.l2_opNorm_mulVec (Aᵀ * A + lam_ * I n)

lemma Ridge_regression_GD.convex (_ : Ridge_regression_GD pro x₀) :
    ConvexOn ℝ Set.univ pro.f := by
  unfold Ridge_regression_problem.f
  exact affine_sq_convex A b

lemma Ridge_regression_GD.point_descent
    (step₂ : alg.t ≤ 1 / pro.l) (xm : EuclideanSpace ℝ (Fin n)) :
    ∀ k : ℕ, pro.f (alg.x (k + 1)) ≤ pro.f xm + 1 / ((2 : ℝ) * alg.t)
      * (‖alg.x k - xm‖ ^ 2 - ‖alg.x (k + 1) - xm‖ ^ 2) := by
  apply point_descent_for_convex (alg := alg.Gradient_Descent) alg.diff alg.smooth alg.convex step₂ xm

-- the O(1/t) descent property of the gradient method
lemma Ridge_regression_GD.gradient_method
    (step₂ : alg.t ≤ 1 / pro.l) (xm : EuclideanSpace ℝ (Fin n)) :
    ∀ k : ℕ, pro.f (alg.x (k + 1)) - pro.f xm ≤ 1 / (2 * (k + 1) * alg.t) * ‖x₀ - xm‖ ^ 2 := by
  apply gradient_method_convergence (alg := alg.Gradient_Descent) alg.diff alg.smooth alg.convex step₂ xm
