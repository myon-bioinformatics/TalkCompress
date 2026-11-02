import unittest

from Zipilogue.rulebook import RuleBook
from Zipilogue.session_cost import measure_session


class SessionCostTests(unittest.TestCase):
    def setUp(self):
        self.book = RuleBook(auto_adopt=False)
        self.phrase = "please run the regression tests before merging"
        self.book.declare(self.phrase, "r1")

    def test_setup_amortization_and_recovery(self):
        one = measure_session(self.book, [self.phrase])
        many = measure_session(self.book, [self.phrase] * 32)
        retry = measure_session(self.book, [self.phrase] * 32,
                                recovery_messages=[self.phrase] * 32)
        self.assertFalse(one["beneficial"])
        self.assertTrue(many["beneficial"])
        self.assertGreater(many["first_saving_turn"], 1)
        self.assertFalse(retry["beneficial"])
        self.assertEqual(retry["compressed_total"] - many["compressed_total"],
                         len(self.phrase.encode()) * 32)

    def test_collision_and_case_loss_are_not_success(self):
        for message in ["r1", self.phrase.upper()]:
            result = measure_session(self.book, [message] * 32)
            self.assertFalse(result["exact_roundtrip"])
            self.assertFalse(result["beneficial"])

    def test_unicode_empty_and_no_mutation(self):
        before = self.book.export_rules()
        result = measure_session(self.book, ["日本語", ""])
        self.assertEqual(result["original_total"], 9)
        self.assertTrue(result["exact_roundtrip"])
        self.assertEqual(before, self.book.export_rules())
        self.assertIsNone(measure_session(self.book, [])["first_saving_turn"])

    def test_counter_and_validation(self):
        result = measure_session(self.book, ["日本語"], count=len, unit="characters")
        self.assertEqual(result["original_total"], 3)
        with self.assertRaises(ValueError):
            measure_session(self.book, ["a"], recovery_messages=[])
        for value in [-1, 1.5, True]:
            with self.assertRaises(ValueError):
                measure_session(self.book, [], count=lambda _: value)
