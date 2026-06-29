/-
  SorryDetect.lean — a Lean 4 command that prints the axiom closure of a declaration in a
  machine-parseable form, so the Python oracle can detect *transitive* `sorry`.

  Why: Lean reports `declaration uses 'sorry'` only as a warning, and only for the immediate
  declaration. A field of an `instance` can be proven by a helper lemma that itself uses `sorry`,
  which the warning misses. `collectAxioms` (the engine behind `#print axioms`) walks the full
  dependency closure and surfaces `sorryAx` wherever it hides.

  Usage in a snippet (the oracle appends this):
      #faithful_axioms LeastSquares_GD.Gradient_Descent
  Output line (grepped by harness/lean_oracle.py via the AXIOMS regex):
      AXIOMS LeastSquares_GD.Gradient_Descent :: [propext, Classical.choice, sorryAx]

  NOTE (verify on v4.13.0): the exact name/signature of the axiom collector can differ across
  Lean versions. The implementation below uses `Lean.collectAxioms`. If that symbol is not present
  in v4.13.0, the project lead can confirm the correct entry point in a `lake env lean` REPL
  (`open Lean in #eval show MetaM _ from do ...`) and adjust. The Python side only depends on the
  printed `AXIOMS <name> :: [...]` line, so only this file changes.
-/
import Lean

open Lean Elab Command

namespace InstanceBEq

/-- Print the axiom closure of `id` as a single parseable line. -/
elab "#faithful_axioms " id:ident : command => do
  let name := id.getId
  -- Ensure the constant exists; if not, emit an explicit marker line.
  match (← getEnv).find? name with
  | none =>
      logInfo m!"AXIOMS {name} :: [UNKNOWN_CONSTANT]"
  | some _ =>
      -- collectAxioms returns the set of axioms `name` transitively depends on.
      let axs ← collectAxioms name
      let names := axs.toList.map (fun n => n.toString)
      logInfo m!"AXIOMS {name} :: [{String.intercalate ", " names}]"

end InstanceBEq
