from __future__ import annotations

import csv
import unittest
from collections import defaultdict
from pathlib import Path

from armproof.demo.queue_guard import QueueGuard, evaluate, features, queue_for_intent


ROOT = Path(__file__).resolve().parents[2]


def split_rows() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    with (ROOT / "data/banking77/source/test.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        source = list(csv.DictReader(stream))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in source:
        grouped[row["category"]].append(row)
    evaluation = []
    training = []
    for rows in grouped.values():
        evaluation.extend(rows[:10])
        training.extend(rows[10:])
    return training, evaluation


class QueueGuardTests(unittest.TestCase):
    def test_features_are_deterministic_unigrams_and_bigrams(self) -> None:
        self.assertEqual(
            features("Card was STOLEN!"),
            ["card", "was", "stolen", "card_was", "was_stolen"],
        )

    def test_training_and_evaluation_splits_do_not_overlap(self) -> None:
        training, evaluation = split_rows()
        self.assertEqual(len(training), 2310)
        self.assertEqual(len(evaluation), 770)
        self.assertFalse(
            {row["text"] for row in training} & {row["text"] for row in evaluation}
        )

    def test_guard_clears_frozen_queue_accuracy_target(self) -> None:
        training, evaluation = split_rows()
        guard = QueueGuard(
            (row["text"], queue_for_intent(row["category"])) for row in training
        )
        correct, total = evaluate(
            guard,
            (
                {"text": row["text"], "queue": queue_for_intent(row["category"])}
                for row in evaluation
            ),
        )
        self.assertEqual((correct, total), (668, 770))
        self.assertGreaterEqual(correct / total, 0.85)


if __name__ == "__main__":
    unittest.main()
