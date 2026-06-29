/-
  Transfer.lean — helpers for theorem-transfer validity (check 3a).

  The Python side synthesizes `example : <T_inst> := by apply <T_abs> ...`. This file can host
  reusable transfer tactics (e.g. discharging the standard convexity/smoothness/step-size
  side-conditions that the Optlib abstract convergence lemmas require) so synthesized proofs stay
  short. the implementation fills these in per structure family.
-/
import Optlib

namespace InstanceBEq
-- (intentionally minimal in the scaffold; structure-specific transfer lemmas go here)
end InstanceBEq
