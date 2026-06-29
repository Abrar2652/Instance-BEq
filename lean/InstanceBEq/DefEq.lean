/-
  DefEq.lean — helpers for definitional-faithfulness equality goals (check 1).

  Provides a `faithful_defeq` macro that bundles the tactic ensemble used to discharge
  `D_gen = D_ref` goals, so the Python side can emit one uniform tactic call. the implementation can
  tune the ensemble here without touching Python.
-/
import Mathlib

namespace InstanceBEq

/-- Tactic ensemble for definitional/extensional equality of two definitions. -/
macro "faithful_defeq" : tactic =>
  `(tactic| first
    | rfl
    | (simp only [] <;> ring)
    | (ext x <;> ring_nf <;> simp)
    | (unfold_let <;> ring)
    | decide)

end InstanceBEq
