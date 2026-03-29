from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from part_b.schemas import CapabilitySnapshotDocument
from services.capability_service import CapabilityService
from services.interview_repo import InterviewRepository


@dataclass
class TrendPoint:
    interview_id: str
    title: str
    target_position: str | None
    updated_at: str
    overall: float
    public_dimensions: dict[str, float]
    weaknesses: list[str]
    summary: str


@dataclass
class TrendHighlights:
    run_count: int
    overall_delta: float
    best_improved_dimension: str | None
    biggest_regression_dimension: str | None


@dataclass
class TrendPayload:
    points: list[TrendPoint]
    dimension_delta: dict[str, float]
    recent_repeated_weaknesses: list[str]
    highlights: TrendHighlights
    summary_markdown: str


class TrendService:
    def __init__(self, repository: InterviewRepository | None = None) -> None:
        self.repository = repository or InterviewRepository()
        self.capability_service = CapabilityService(repository=self.repository)

    def build_payload(self, *, limit: int | None = None) -> TrendPayload:
        points = self._load_points(limit=limit)
        dimension_delta = self._dimension_delta(points)
        highlights = self._build_highlights(points, dimension_delta)
        recent_repeated_weaknesses = self._recent_repeated_weaknesses(points)
        payload = TrendPayload(
            points=points,
            dimension_delta=dimension_delta,
            recent_repeated_weaknesses=recent_repeated_weaknesses,
            highlights=highlights,
            summary_markdown="",
        )
        payload.summary_markdown = self.render_markdown(payload)
        return payload

    def export_payload(self, payload: TrendPayload) -> dict[str, object]:
        return {
            "highlights": {
                "run_count": payload.highlights.run_count,
                "overall_delta": payload.highlights.overall_delta,
                "best_improved_dimension": payload.highlights.best_improved_dimension,
                "biggest_regression_dimension": payload.highlights.biggest_regression_dimension,
            },
            "dimension_delta": payload.dimension_delta,
            "recent_repeated_weaknesses": payload.recent_repeated_weaknesses,
            "points": [
                {
                    "interview_id": point.interview_id,
                    "title": point.title,
                    "target_position": point.target_position,
                    "updated_at": point.updated_at,
                    "overall": point.overall,
                    "public_dimensions": point.public_dimensions,
                    "weaknesses": point.weaknesses,
                    "summary": point.summary,
                }
                for point in payload.points
            ],
            "summary_markdown": payload.summary_markdown,
        }

    def render_markdown(self, payload: TrendPayload) -> str:
        lines = [
            "# 面试趋势",
            "",
            f"- run_count: {payload.highlights.run_count}",
            f"- overall_delta: {payload.highlights.overall_delta:+.1f}",
            f"- best_improved_dimension: {payload.highlights.best_improved_dimension or '暂无'}",
            f"- biggest_regression_dimension: {payload.highlights.biggest_regression_dimension or '暂无'}",
            "",
            "## 维度变化",
            "",
            "| 维度 | Delta |",
            "| --- | --- |",
        ]
        for name, delta in payload.dimension_delta.items():
            lines.append(f"| {name} | {delta:+.1f} |")
        lines.extend(["", "## 最近重复问题", ""])
        lines.extend(self._bullet_block(payload.recent_repeated_weaknesses))
        lines.extend(["", "## 时间线", "", "| interview_id | title | overall | updated_at |", "| --- | --- | --- | --- |"])
        for point in payload.points:
            lines.append(f"| {point.interview_id} | {point.title} | {point.overall:.1f} | {point.updated_at} |")
        return "\n".join(lines).strip() + "\n"

    def _load_points(self, *, limit: int | None = None) -> list[TrendPoint]:
        points: list[TrendPoint] = []
        for item in self.repository.list_all():
            meta = self.repository.load_meta(item.interview_id)
            analyses = self.repository.load_analyses(item.interview_id)
            snapshot = self._load_or_build_snapshot(item.interview_id)
            if snapshot is None:
                continue
            overall = self._overall_score(snapshot, analyses)
            public_dimensions = dict(snapshot.public_dimensions)
            public_dimensions.setdefault("overall", overall)
            points.append(
                TrendPoint(
                    interview_id=item.interview_id,
                    title=meta.title if meta and meta.title else item.interview_id,
                    target_position=meta.target_position if meta else None,
                    updated_at=snapshot.updated_at,
                    overall=overall,
                    public_dimensions=public_dimensions,
                    weaknesses=snapshot.weaknesses,
                    summary=snapshot.summary,
                )
            )
        points.sort(key=lambda point: self._sort_key(point.updated_at))
        if limit is not None and limit > 0:
            points = points[-limit:]
        return points

    def _load_or_build_snapshot(self, interview_id: str) -> CapabilitySnapshotDocument | None:
        snapshot = self.repository.load_capability_snapshot(interview_id)
        if snapshot is not None:
            return snapshot
        if self.repository.load_analyses(interview_id) is None:
            return None
        return self.capability_service.refresh_snapshot(interview_id)

    def _overall_score(self, snapshot: CapabilitySnapshotDocument, analyses) -> float:
        if analyses is not None and analyses.summary is not None:
            value = analyses.summary.average_scores.get("weighted_total")
            if value is not None:
                return round(float(value), 1)
        if "overall" in snapshot.public_dimensions:
            return float(snapshot.public_dimensions["overall"])
        return 0.0

    def _dimension_delta(self, points: list[TrendPoint]) -> dict[str, float]:
        if len(points) < 2:
            baseline = points[0].public_dimensions if points else {}
            return {name: 0.0 for name in baseline}
        before = points[0].public_dimensions
        after = points[-1].public_dimensions
        names = sorted(set(before) | set(after))
        return {
            name: round(after.get(name, 0.0) - before.get(name, 0.0), 1)
            for name in names
        }

    def _build_highlights(self, points: list[TrendPoint], dimension_delta: dict[str, float]) -> TrendHighlights:
        overall_delta = 0.0
        if len(points) >= 2:
            overall_delta = round(points[-1].overall - points[0].overall, 1)

        best_improved_dimension = None
        positive_dimensions = {name: delta for name, delta in dimension_delta.items() if delta > 0 and name != "overall"}
        if positive_dimensions:
            best_improved_dimension = max(positive_dimensions, key=positive_dimensions.get)

        biggest_regression_dimension = None
        negative_dimensions = {name: delta for name, delta in dimension_delta.items() if delta < 0 and name != "overall"}
        if negative_dimensions:
            biggest_regression_dimension = min(negative_dimensions, key=negative_dimensions.get)

        return TrendHighlights(
            run_count=len(points),
            overall_delta=overall_delta,
            best_improved_dimension=best_improved_dimension,
            biggest_regression_dimension=biggest_regression_dimension,
        )

    def _recent_repeated_weaknesses(self, points: list[TrendPoint], *, recent_window: int = 3, limit: int = 5) -> list[str]:
        recent_points = points[-recent_window:]
        counter = Counter(
            weakness.strip()
            for point in recent_points
            for weakness in point.weaknesses
            if weakness and weakness.strip()
        )
        return [item for item, count in counter.most_common(limit) if count >= 2] or [item for item, _ in counter.most_common(limit)]

    def _bullet_block(self, items: list[str]) -> list[str]:
        return [f"- {item}" for item in items] or ["- 暂无"]

    def _sort_key(self, value: str) -> tuple[int, str]:
        try:
            return (0, datetime.fromisoformat(value).isoformat())
        except ValueError:
            return (1, value)
