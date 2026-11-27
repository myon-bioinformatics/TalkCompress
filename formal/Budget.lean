import Std

/-!
The character-budget controller in DensityFacadeRoute.run_budget.

`size` measures characters, not bytes, tokenizer tokens, or semantic fidelity.
`step` models one pipeline call that returns normally; the fuel bound does not
prove termination of arbitrary external transforms. The Python connection
tests exercise the actual controller and the real C/E pipeline separately.
-/

namespace TalkCompress

variable {Candidate : Type}

/-- Evaluated candidates; stop at the budget, on no shrink, or when fuel ends. -/
def candidates (size : Candidate → Nat) (step : Candidate → Candidate)
    (budget : Nat) : Nat → Candidate → List Candidate
  | 0, _ => []
  | fuel + 1, current =>
      if size current ≤ budget then []
      else
        let next := step current
        if size current ≤ size next then [next]
        else next :: candidates size step budget fuel next

/-- Keep the first shortest observation, including the original input. -/
def shortest (size : Candidate → Nat) : Candidate → List Candidate → Candidate
  | best, [] => best
  | best, next :: rest =>
      shortest size (if size next < size best then next else best) rest

def budgetResult (size : Candidate → Nat) (step : Candidate → Candidate)
    (budget fuel : Nat) (original : Candidate) : Candidate :=
  shortest size original (candidates size step budget fuel original)

theorem candidate_count_bounded (size : Candidate → Nat)
    (step : Candidate → Candidate) (budget fuel : Nat) (current : Candidate) :
    (candidates size step budget fuel current).length ≤ fuel := by
  induction fuel generalizing current with
  | zero => simp [candidates]
  | succ fuel ih =>
      simp only [candidates]
      split
      · simp
      · split
        · simp
        · simp only [List.length_cons]
          have bound := ih (step current)
          omega

theorem shortest_not_larger (size : Candidate → Nat)
    (best : Candidate) (observed : List Candidate) :
    size (shortest size best observed) ≤ size best := by
  induction observed generalizing best with
  | nil => simp [shortest]
  | cons next rest ih =>
      simp only [shortest]
      by_cases better : size next < size best
      · simp only [ite_eq_left better]
        exact Nat.le_trans (ih next) (Nat.le_of_lt better)
      · simpa only [ite_eq_right better] using ih best

theorem shortest_is_minimum (size : Candidate → Nat)
    (best item : Candidate) (observed : List Candidate) (present : item ∈ observed) :
    size (shortest size best observed) ≤ size item := by
  induction observed generalizing best with
  | nil => simp at present
  | cons next rest ih =>
      rcases List.mem_cons.mp present with same | later
      · subst item
        simp only [shortest]
        by_cases better : size next < size best
        · simpa only [ite_eq_left better] using shortest_not_larger size next rest
        · simp only [ite_eq_right better]
          have bound := shortest_not_larger size best rest
          omega
      · simpa only [shortest] using
          ih (if size next < size best then next else best) later

theorem no_improvement_keeps_original (size : Candidate → Nat)
    (best : Candidate) (observed : List Candidate)
    (no_better : ∀ item ∈ observed, size best ≤ size item) :
    shortest size best observed = best := by
  induction observed with
  | nil => rfl
  | cons next rest ih =>
      have next_bound := no_better next (by simp)
      have not_better : ¬size next < size best := by omega
      simp only [shortest, ite_eq_right not_better]
      apply ih
      intro item present
      exact no_better item (List.mem_cons_of_mem next present)

theorem within_budget_skips_pipeline (size : Candidate → Nat)
    (step : Candidate → Candidate) (budget fuel : Nat) (original : Candidate)
    (within : size original ≤ budget) :
    candidates size step budget fuel original = [] := by
  cases fuel <;> simp [candidates, within]

theorem budget_result_not_larger (size : Candidate → Nat)
    (step : Candidate → Candidate) (budget fuel : Nat) (original : Candidate) :
    size (budgetResult size step budget fuel original) ≤ size original := by
  exact shortest_not_larger size original _

end TalkCompress
