from __future__ import annotations

from dataclasses import dataclass

from core.exceptions import ProjectError
from part_b.schemas import AnalysesDocument, CapabilitySnapshotDocument, CompareResultDocument
from services.capability_service import CapabilityService
from services.interview_repo import InterviewRepository


@dataclass
class TopicComparison:
    topic_key: str
    score_a: float
    score_b: float
    delta: float
    summary_a: str
    summary_b: str


@dataclass
class ComparePayload:
    interview_id_a: str
    interview_id_b: str
    analyses_a: AnalysesDocument
    analyses_b: AnalysesDocument
    snapshot_a: CapabilitySnapshotDocument
    snapshot_b: CapabilitySnapshotDocument
    result: CompareResultDocument
    public_dimension_delta: dict[str, float]
    role_dimension_delta: dict[str, float]
    topic_deltas: list[TopicComparison]
    summary_markdown: str


class CompareService:
    def __init__(self, repository: InterviewRepository | None = None) -> None:
        self.repository = repository or InterviewRepository()
        self.capability_service = CapabilityService(repository=self.repository)

    def compare(self, id_a: str, id_b: str) -> ComparePayload:
        analyses_a = self.repository.load_analyses(id_a)
        analyses_b = self.repository.load_analyses(id_b)
        if analyses_a is None or analyses_b is None:
            raise ProjectError(f"能力对比需要两场面试都已经生成 analyses.json: {id_a}, {id_b}")

        snapshot_a = self.repository.load_capability_snapshot(id_a) or self.capability_service.refresh_snapshot(id_a)
        snapshot_b = self.repository.load_capability_snapshot(id_b) or self.capability_service.refresh_snapshot(id_b)
        public_dimension_delta = self._dimension_delta(snapshot_a.public_dimensions, snapshot_b.public_dimensions)
        role_dimension_delta = self._dimension_delta(snapshot_a.role_dimensions, snapshot_b.role_dimensions)
        topic_deltas = self._topic_deltas(analyses_a, analyses_b)
        result = self._result_document(
            id_a=id_a,
            id_b=id_b,
            analyses_a=analyses_a,
            analyses_b=analyses_b,
            snapshot_a=snapshot_a,
            snapshot_b=snapshot_b,
            public_dimension_delta=public_dimension_delta,
            role_dimension_delta=role_dimension_delta,
            topic_deltas=topic_deltas,
        )
        return ComparePayload(
            interview_id_a=id_a,
            interview_id_b=id_b,
            analyses_a=analyses_a,
            analyses_b=analyses_b,
            snapshot_a=snapshot_a,
            snapshot_b=snapshot_b,
            result=result,
            public_dimension_delta=public_dimension_delta,
            role_dimension_delta=role_dimension_delta,
            topic_deltas=topic_deltas,
            summary_markdown=self.render_markdown(result, public_dimension_delta, role_dimension_delta, topic_deltas),
        )

    def render_markdown(
        self,
        result: CompareResultDocument,
        public_dimension_delta: dict[str, float],
        role_dimension_delta: dict[str, float],
        topic_deltas: list[TopicComparison],
    ) -> str:
        lines = [
            "# 面试对比",
            "",
            f"- interview_id_a: {result.interview_id_a}",
            f"- interview_id_b: {result.interview_id_b}",
            "",
            "## 进步点",
            "",
            *self._bullet_block(result.improvements),
            "",
            "## 回退点",
            "",
            *self._bullet_block(result.regressions),
            "",
            "## 重复问题",
            "",
            *self._bullet_block(result.repeated_issues),
            "",
            "## 下一步聚焦",
            "",
            *self._bullet_block(result.next_focus),
            "",
            "## 公共维度变化",
            "",
            "| 维度 | Delta |",
            "| --- | --- |",
        ]
        for name, delta in public_dimension_delta.items():
            lines.append(f"| {name} | {delta:+.1f} |")
        if role_dimension_delta:
            lines.extend(["", "## 题型/岗位维度变化", "", "| 维度 | Delta |", "| --- | --- |"])
            for name, delta in role_dimension_delta.items():
                lines.append(f"| {name} | {delta:+.1f} |")
        if topic_deltas:
            lines.extend(["", "## 题目层变化", ""])
            for item in topic_deltas:
                lines.append(f"### {item.topic_key}")
                lines.append("")
                lines.append(f"- score_a: {item.score_a}")
                lines.append(f"- score_b: {item.score_b}")
                lines.append(f"- delta: {item.delta:+.1f}")
                lines.append(f"- summary_a: {item.summary_a}")
                lines.append(f"- summary_b: {item.summary_b}")
                lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _result_document(
        self,
        *,
        id_a: str,
        id_b: str,
        analyses_a: AnalysesDocument,
        analyses_b: AnalysesDocument,
        snapshot_a: CapabilitySnapshotDocument,
        snapshot_b: CapabilitySnapshotDocument,
        public_dimension_delta: dict[str, float],
        role_dimension_delta: dict[str, float],
        topic_deltas: list[TopicComparison],
    ) -> CompareResultDocument:
        improvements = [
            f"{name} 提升 {delta:+.1f}"
            for name, delta in public_dimension_delta.items()
            if delta >= 0.4
        ]
        regressions = [
            f"{name} 回落 {delta:+.1f}"
            for name, delta in public_dimension_delta.items()
            if delta <= -0.4
        ]
        repeated_issues = sorted(set(snapshot_a.weaknesses) & set(snapshot_b.weaknesses))[:5]
        repeated_issues.extend(
            item.topic_key
            for item in topic_deltas
            if item.delta <= -0.4 and item.topic_key not in repeated_issues
        )
        next_focus = self._next_focus(snapshot_b, regressions, repeated_issues)
        if not improvements and analyses_a.summary and analyses_b.summary:
            before = analyses_a.summary.average_scores.get("weighted_total", 0.0)
            after = analyses_b.summary.average_scores.get("weighted_total", 0.0)
            delta = round(after - before, 1)
            if delta > 0:
                improvements.append(f"整体表现提升 {delta:+.1f}")
            elif delta < 0:
                regressions.append(f"整体表现回落 {delta:+.1f}")
        return CompareResultDocument(
            interview_id_a=id_a,
            interview_id_b=id_b,
            improvements=improvements,
            regressions=regressions,
            repeated_issues=repeated_issues[:6],
            next_focus=next_focus[:6],
        )

    def _topic_deltas(self, analyses_a: AnalysesDocument, analyses_b: AnalysesDocument) -> list[TopicComparison]:
        keyed_a = {analysis.main_question: analysis for analysis in analyses_a.analyses}
        keyed_b = {analysis.main_question: analysis for analysis in analyses_b.analyses}
        topic_keys = sorted(set(keyed_a) & set(keyed_b))
        deltas: list[TopicComparison] = []
        for key in topic_keys:
            analysis_a = keyed_a[key]
            analysis_b = keyed_b[key]
            delta = round(analysis_b.rubric.weighted_total() - analysis_a.rubric.weighted_total(), 1)
            deltas.append(
                TopicComparison(
                    topic_key=key,
                    score_a=analysis_a.rubric.weighted_total(),
                    score_b=analysis_b.rubric.weighted_total(),
                    delta=delta,
                    summary_a="；".join(analysis_a.weaknesses[:2] or analysis_a.strengths[:2]) or "暂无",
                    summary_b="；".join(analysis_b.weaknesses[:2] or analysis_b.strengths[:2]) or "暂无",
                )
            )
        return deltas

    def _dimension_delta(self, before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
        names = sorted(set(before) | set(after))
        return {
            name: round(after.get(name, 0.0) - before.get(name, 0.0), 1)
            for name in names
        }

    def _next_focus(
        self,
        snapshot_b: CapabilitySnapshotDocument,
        regressions: list[str],
        repeated_issues: list[str],
    ) -> list[str]:
        focus = []
        focus.extend(snapshot_b.next_focus)
        focus.extend(regressions)
        focus.extend(repeated_issues)
        deduped: list[str] = []
        for item in focus:
            normalized = item.strip()
            if normalized and normalized not in deduped:
                deduped.append(normalized)
        return deduped

    def _bullet_block(self, items: list[str]) -> list[str]:
        return [f"- {item}" for item in items] or ["- 暂无"]
