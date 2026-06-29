import Optlib.Autoformalization.Lemmas
import Optlib.Autoformalization.Template.GD_template

open Set Real Matrix Finset Filter Bornology BigOperators Topology Classical


noncomputable section Logistic_regression

local notation "Fin n" => Fin n

local notation "‖" x "‖₂" => @Norm.norm _ (PiLp.instNorm 2 fun _ ↦ ℝ) x
local notation "‖" x "‖₁" => @Norm.norm _ (PiLp.instNorm 1 fun _ ↦ ℝ) x
local notation "|‖" A "|‖" => ‖(Matrix.toEuclideanLin ≪≫ₗ LinearMap.toContinuousLinearMap) A‖₊

class Logistic_regression_problem (A : Matrix (Fin m) (Fin n) ℝ) (b : Fin m → ℝ) where
  hA : A ≠ 0

variable {A : Matrix (Fin m) (Fin n) ℝ} {b : Fin m → ℝ}

def Logistic_regression_problem.f (_ : Logistic_regression_problem A b) : EuclideanSpace ℝ (Fin n) → ℝ :=
  fun x ↦ ∑ i in Finset.univ, log(1 + exp(-b i * Fin.map_indexed (lam i a, a • x) A))

def Logistic_regression_problem.l (_ : Logistic_regression_problem A b) : NNReal := 1

instance Logistic_regression_problem.unconstrained_problem (self : Logistic_regression_problem A b) :
    unconstrained_problem self.f where

variable {pro : Logistic_regression_problem A b}

class Logistic_regression_GD (pro : Logistic_regression_problem A b) (x₀ : EuclideanSpace ℝ (Fin n)) where
  t : ℝ
  x : ℕ → EuclideanSpace ℝ (Fin n)
  ht : t > 0
  update : ∀ k : ℕ,
    let aik : Fin m → ℝ := lam i, (A i, k) • x k
    let grad : EuclideanSpace ℝ (Fin n) := ∑ i in Finset.univ, (-b i * Fin.map_indexed aik A) / (1 + exp(b i * Fin.map_indexed aik A))
    x (k + 1) = x k - t • grad
  initial : x 0 = x₀

lemma Logistic_regression_problem.hasGradient (self : Logistic_regression_problem A b) :
    ∀ x, HasGradientAt self.f (lam i, -b i * Fin.map_indexed (lam i a, a • x) A / (1 + exp(b i * Fin.map_indexed (lam i a, a • x) A))) x := by
  -- This lemma needs to be filled in with appropriate logic
  sorry

lemma Logistic_regression_problem.gradient_f (self : Logistic_regression_problem A b) :
    ∀ x, gradient self.f x = ∑ i in Finset.univ, (-b i * Fin.map_indexed (lam i a, a • x) A / (1 + exp(b i * Fin.map_indexed (lam i a, a • x) A))) := by
  -- This lemma needs to be filled in with appropriate logic
  sorry

lemma Logistic_regression_problem.pos_l (self : Logistic_regression_problem A b) :
    self.l > 0 := by
  unfold Logistic_regression_problem.l; simp
  -- This lemma needs to be filled in with appropriate logic
  sorry

lemma Logistic_regression_GD.update_cor (self : Logistic_regression_GD pro x₀) :
    ∀ (k : ℕ), self.x (k + 1) = self.x k - self.t • gradient pro.f (self.x k) := by
  intro k
  rw [self.update k]
  rw [pro.gradient_f]
  -- This lemma needs to be filled in with appropriate logic
  sorry

instance Logistic_regression_GD.Gradient_Descent (self : Logistic_regression_GD pro x₀) :
    Gradient_Descent (Logistic_regression_problem.unconstrained_problem pro) x₀ where
  x := self.x
  t := self.t
  l := pro.l
  update := self.update_cor
  hl := pro.pos_l
  step₁ := self.ht
  initial := self.initial

variable {alg : Logistic_regression_GD pro x₀}

lemma Logistic_regression_GD.diff (_ : Logistic_regression_GD pro x₀) :
    Differentiable ℝ pro.f := by
  -- This lemma needs to be filled in with appropriate logic
  sorry

lemma Logistic_regression_GD.smooth (_ : Logistic_regression_GD pro x₀) :
    LipschitzWith pro.l (gradient pro.f) := by
  -- This lemma needs to be filled in with appropriate logic
  sorry

lemma Logistic_regression_GD.convex (_ : Logistic_regression_GD pro x₀) :
    ConvexOn ℝ Set.univ pro.f := by
  -- This lemma needs to be filled in with appropriate logic
  sorry

lemma Logistic_regression_GD.point_descent
    (step₂ : alg.t ≤ 1 / pro.l) (xm : EuclideanSpace ℝ (Fin n)) :
    ∀ k : ℕ, pro.f (alg.x (k + 1)) ≤ pro.f xm + 1 / ((2 : ℝ) * alg.t)
      * (‖alg.x k - xm‖ ^ 2 - ‖alg.x (k + 1) - xm‖ ^ 2) := by
  apply point_descent_for_convex (alg := alg.Gradient_Descent) alg.diff alg.smooth alg.convex step₂ xm

-- the O(1/t) descent property of the gradient method
lemma Logistic_regression_GD.gradient_method
    (step₂ : alg.t ≤ 1 / pro.l) (xm : EuclideanSpace ℝ (Fin n)) :
    ∀ k : ℕ, pro.f (alg.x (k + 1)) - pro.f xm ≤ 1 / (2 * (k + 1) * alg.t) * ‖x₀ - xm‖ ^ 2 := by
  apply gradient_method_convergence (alg := alg.Gradient_Descent) alg.diff alg.smooth alg.convex step₂ xm

end Logistic_regression
