"""Connect the Lean budget model to the actual Python controller.

Controlled pipeline outputs cover the controller's boundary cases. Separate
checks route through the real C/E transforms. These finite tests do not prove
Python semantics, natural-language fidelity, or token/byte compression.
"""

import argparse
from contextlib import redirect_stderr
import io
import itertools
import json
import unittest
from unittest.mock import patch

from DensityFacadeRoute import density_facade_route as router


class FormalBudgetBridge(unittest.TestCase):
    def test_all_small_length_transitions_keep_the_first_shortest_observation(self):
        # All 4^4 possible transitions between lengths 0..3, from each initial
        # length and with each budget: 4,096 concrete controller executions.
        for table in itertools.product(range(4), repeat=4):
            for initial_length, budget in itertools.product(range(4), repeat=2):
                with self.subTest(table=table, initial_length=initial_length, budget=budget):
                    original = "o" * initial_length
                    observed = []

                    def transform(layers, current, args, *, trace=None):
                        candidate = "x" * table[len(current)]
                        observed.append(candidate)
                        return candidate

                    with patch.object(router, "run_pipeline", side_effect=transform):
                        result = router.run_budget(
                            original, argparse.Namespace(), budget=budget, layers=["identity"]
                        )
                    self.assertLessEqual(len(observed), 8)
                    self.assertLessEqual(len(result), len(original))
                    self.assertEqual(result, min([original, *observed], key=len))
                    if initial_length <= budget:
                        self.assertEqual(observed, [])

    def test_eight_round_limit_does_not_claim_that_budget_was_reached(self):
        original = "abcdefghijklmnop"
        stderr = io.StringIO()
        with patch.object(router, "run_pipeline", side_effect=lambda layers, text, args, **kw: text[:-1]) as step, \
                redirect_stderr(stderr):
            result = router.run_budget(
                original, argparse.Namespace(stats=True), budget=0, layers=["identity"]
            )
        report = json.loads(stderr.getvalue())
        self.assertEqual(step.call_count, 8)
        self.assertEqual(result, original[:8])
        self.assertEqual(report["steps"], 8)
        self.assertFalse(report["under_budget"])

    def test_no_shrink_stops_before_a_later_unobserved_improvement(self):
        # Only evaluated candidates participate in the minimum. A later better
        # candidate must not be used after the no-shrink stopping condition.
        with patch.object(router, "run_pipeline", side_effect=["short", "growing again", "x"]) as step:
            result = router.run_budget(
                "initially long text", argparse.Namespace(), budget=0, layers=["identity"]
            )
        self.assertEqual(step.call_count, 2)
        self.assertEqual(result, "short")

    def test_equal_size_and_growth_keep_original_content(self):
        for candidate in ("xyz", "longer"):
            with self.subTest(candidate=candidate), \
                    patch.object(router, "run_pipeline", return_value=candidate) as step:
                result = router.run_budget("abc", argparse.Namespace(), budget=0, layers=["identity"])
                self.assertEqual(result, "abc")
                self.assertEqual(step.call_count, 1)

    def test_budget_counts_python_characters_not_utf8_bytes(self):
        # Astral characters and combining sequences distinguish the metrics.
        for original in ("😀", "e\u0301", "日本語", "😀e\u0301"):
            with self.subTest(original=original), patch.object(router, "run_pipeline") as step:
                self.assertGreater(len(original.encode("utf-8")), len(original))
                result = router.run_budget(
                    original, argparse.Namespace(), budget=len(original), layers=["identity"]
                )
                self.assertEqual(result, original)
                step.assert_not_called()

    def test_real_c_and_e_pipeline_obeys_the_same_selection_contract(self):
        samples = (
            "um thank you for your information please let me know as soon as possible",
            "for your information\nthank you\n",
            "私は ready and waiting",
            "😀 café e\u0301",
            "xyzzy",
            "",
        )
        pipeline = router.run_pipeline
        for original in samples:
            for budget in (0, len(original) // 2, len(original)):
                with self.subTest(original=original, budget=budget):
                    observed = []
                    args = argparse.Namespace(state=None, mode="compress", stats=False)

                    def record(layers, current, options, *, trace=None):
                        candidate = pipeline(layers, current, options, trace=trace)
                        observed.append(candidate)
                        return candidate

                    with patch.object(router, "run_pipeline", side_effect=record):
                        result = router.run_budget(original, args, budget=budget, layers=["C", "E"])
                    self.assertLessEqual(len(observed), 8)
                    self.assertEqual(result, min([original, *observed], key=len))
                    self.assertLessEqual(len(result), len(original))


if __name__ == "__main__":
    unittest.main()
