"""Scorer engine for OpenLLM"""

import time
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelScore:
    """Score for a model"""

    model_name: str
    quality_score: float = 0.5
    speed_score: float = 0.5
    context_score: float = 0.5
    reliability_score: float = 0.5
    total_score: float = 0.5
    last_updated: datetime = None

    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()
        self.total_score = (
            self.quality_score * 0.4
            + self.speed_score * 0.3
            + self.context_score * 0.2
            + self.reliability_score * 0.1
        )


class ScorerEngine:
    """Engine for scoring models"""

    def __init__(self):
        self._scores: dict[str, ModelScore] = {}
        self._request_times: dict[str, list[float]] = {}
        self._success_counts: dict[str, int] = {}
        self._failure_counts: dict[str, int] = {}

    def calculate_score(
        self,
        model_name: str,
        response_time: float,
        success: bool,
        context_length: int = 0,
        base_score: float = 0.5,
    ) -> ModelScore:
        if model_name not in self._scores:
            self._scores[model_name] = ModelScore(model_name=model_name)

        score = self._scores[model_name]

        if model_name not in self._request_times:
            self._request_times[model_name] = []
        self._request_times[model_name].append(response_time)

        if len(self._request_times[model_name]) > 100:
            self._request_times[model_name] = self._request_times[model_name][-100:]

        if success:
            self._success_counts[model_name] = self._success_counts.get(model_name, 0) + 1
        else:
            self._failure_counts[model_name] = self._failure_counts.get(model_name, 0) + 1

        avg_response_time = sum(self._request_times[model_name]) / len(
            self._request_times[model_name]
        )

        speed_score = min(1.0, 1.0 / (avg_response_time + 0.1))

        total_requests = self._success_counts.get(model_name, 0) + self._failure_counts.get(
            model_name, 0
        )
        if total_requests > 0:
            reliability = self._success_counts[model_name] / total_requests
        else:
            reliability = 0.5

        context_score = min(1.0, context_length / 128000)

        score.quality_score = base_score
        score.speed_score = speed_score
        score.context_score = context_score
        score.reliability_score = reliability
        score.last_updated = datetime.now()

        score.total_score = (
            score.quality_score * 0.4
            + score.speed_score * 0.3
            + score.context_score * 0.2
            + score.reliability_score * 0.1
        )

        return score

    def get_score(self, model_name: str) -> Optional[ModelScore]:
        return self._scores.get(model_name)

    def get_ranked_models(self) -> list[ModelScore]:
        scores = list(self._scores.values())
        scores.sort(key=lambda s: s.total_score, reverse=True)
        return scores

    def get_best_model(
        self,
        enabled_models: list[str],
        model_type: Optional[str] = None,
        model_scale: Optional[str] = None,
    ) -> str:
        if not enabled_models:
            return "meta-model"

        ranked = self.get_ranked_models()
        for score in ranked:
            if score.model_name in enabled_models:
                return score.model_name

        return enabled_models[0] if enabled_models else "meta-model"

    def record_failure(self, model_name: str):
        self._failure_counts[model_name] = self._failure_counts.get(model_name, 0) + 1

    def record_success(self, model_name: str):
        self._success_counts[model_name] = self._success_counts.get(model_name, 0) + 1


_scorer_instance: Optional[ScorerEngine] = None


def get_scorer() -> ScorerEngine:
    """Get global scorer engine"""
    global _scorer_instance
    if _scorer_instance is None:
        _scorer_instance = ScorerEngine()
    return _scorer_instance
