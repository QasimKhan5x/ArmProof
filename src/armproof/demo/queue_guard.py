"""Dependency-free operational queue guard for the SurgeDesk reference app."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping


TOKEN_RE = re.compile(r"[a-z0-9]+")


def queue_for_intent(intent: str | None) -> str:
    """Map a BANKING77 intent into SurgeDesk's operational queue."""
    if intent is None:
        return "Manual review"
    if intent in {
        "lost_or_stolen_card",
        "compromised_card",
        "card_payment_not_recognised",
        "cash_withdrawal_not_recognised",
        "direct_debit_payment_not_recognised",
        "lost_or_stolen_phone",
    }:
        return "Account security"
    if "cash_withdrawal" in intent or intent in {
        "atm_support", "cash_withdrawal_charge", "card_swallowed",
    }:
        return "Cash & ATM"
    if "transfer" in intent or intent in {"beneficiary_not_allowed", "receiving_money"}:
        return "Transfers"
    if "card" in intent:
        return "Cards & payments"
    return "Account support"


def features(text: str) -> list[str]:
    words = TOKEN_RE.findall(text.lower())
    return words + [f"{left}_{right}" for left, right in zip(words, words[1:])]


@dataclass(frozen=True)
class QueuePrediction:
    queue: str
    margin: float


class QueueGuard:
    """Multinomial Naive Bayes classifier with deterministic Laplace smoothing."""

    def __init__(self, rows: Iterable[tuple[str, str]]) -> None:
        examples = list(rows)
        if not examples:
            raise ValueError("queue guard requires training examples")
        self.class_counts: Counter[str] = Counter()
        self.feature_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.feature_totals: Counter[str] = Counter()
        self.vocabulary: set[str] = set()
        for text, queue in examples:
            tokens = features(text)
            self.class_counts[queue] += 1
            self.feature_counts[queue].update(tokens)
            self.feature_totals[queue] += len(tokens)
            self.vocabulary.update(tokens)
        self.example_count = len(examples)
        self.classes = tuple(sorted(self.class_counts))

    def _score(self, text: str, queue: str) -> float:
        vocabulary_size = len(self.vocabulary)
        score = math.log(self.class_counts[queue] / self.example_count)
        denominator = self.feature_totals[queue] + vocabulary_size
        for token in features(text):
            score += math.log((self.feature_counts[queue][token] + 1) / denominator)
        return score

    def predict(self, text: str) -> QueuePrediction:
        scores = sorted(
            ((self._score(text, queue), queue) for queue in self.classes),
            reverse=True,
        )
        margin = scores[0][0] - scores[1][0] if len(scores) > 1 else math.inf
        return QueuePrediction(queue=scores[0][1], margin=margin)


def evaluate(
    guard: QueueGuard,
    rows: Iterable[Mapping[str, str]],
) -> tuple[int, int]:
    examples = list(rows)
    correct = sum(
        guard.predict(row["text"]).queue == row["queue"] for row in examples
    )
    return correct, len(examples)
