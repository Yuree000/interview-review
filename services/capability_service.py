from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from core.exceptions import ProjectError
from core.time_utils import utc_now_iso
from part_b.schemas import (
    AnalysesDocument,
    CapabilitySnapshotDocument,
    GlobalProfileDocument,
    InterviewMetaDocument,
    TopicAnalysis,
)
from services.interview_repo import InterviewRepository
from services.profile_service import ProfileService


PUBLIC_DIMENSION_BUILDERS = {
    "communication": lambda analysis: round((analysis.rubric.structure + analysis.rubric.completeness) / 2, 1),
    "problem_solving": lambda analysis: round((analysis.rubric.depth + analysis.rubric.accuracy) / 2, 1),
    "role_fit": lambda analysis: float(analysis.rubric.position_fit),
    "delivery": lambda analysis: round((analysis.rubric.completeness + analysis.rubric.position_fit) / 2, 1),
    "followup": lambda analysis: float(
        analysis.rubric.followup_handling if analysis.rubric.followup_handling is not None else analysis.rubric.weighted_total()
    ),
}


@dataclass
class CapabilityArtifacts:
    snapshot: CapabilitySnapshotDocument
    global_profile: GlobalProfileDocument
    global_profile_markdown: str


class CapabilityService:
    def __init__(
        self,
        repository: InterviewRepository | None = None,
        profile_service: ProfileService | None = None,
    ) -> None:
        self.repository = repository or InterviewRepository()
        self.profile_service = profile_service or ProfileService(output_root=self.repository.output_root)

    def build_snapshot(
        self,
        *,
        interview_id: str,
        analyses: AnalysesDocument,
        meta: InterviewMetaDocument | None = None,
    ) -> CapabilitySnapshotDocument:
        public_dimensions = self._public_dimensions(analyses.analyses)
        role_dimensions = self._role_dimensions(analyses.analyses)
        strengths = self._top_items(item for analysis in analyses.analyses for item in analysis.strengths)
        weaknesses = self._top_items(item for analysis in analyses.analyses for item in analysis.weaknesses)
        next_focus = self._next_focus(weaknesses)
        summary = self._snapshot_summary(
            public_dimensions=public_dimensions,
            strengths=strengths,
            weaknesses=weaknesses,
            meta=meta,
        )
        return CapabilitySnapshotDocument(
            interview_id=interview_id,
            public_dimensions=public_dimensions,
            role_dimensions=role_dimensions,
            strengths=strengths,
            weaknesses=weaknesses,
            next_focus=next_focus,
            summary=summary,
            updated_at=utc_now_iso(),
        )

    def refresh_snapshot(self, interview_id: str) -> CapabilitySnapshotDocument:
        analyses = self.repository.load_analyses(interview_id)
        if analyses is None:
            raise ProjectError(f"能力快照需要先生成 analyses.json: {interview_id}")
        meta = self.repository.load_meta(interview_id)
        snapshot = self.build_snapshot(interview_id=interview_id, analyses=analyses, meta=meta)
        self.repository.save_capability_snapshot(snapshot)
        return snapshot

    def refresh_global_profile(self) -> CapabilityArtifacts:
        snapshots = self._load_or_build_snapshots()
        if not snapshots:
            raise ProjectError("全局画像需要至少一场已完成 PH4 的面试。")

        metas = {
            snapshot.interview_id: self.repository.load_meta(snapshot.interview_id)
            for snapshot in snapshots
        }
        public_dimensions = self._aggregate_public_dimensions(snapshots)
        role_dimensions = self._aggregate_role_dimensions(snapshots, metas)
        strengths = self._top_items(item for snapshot in snapshots for item in snapshot.strengths)
        weaknesses = self._top_items(item for snapshot in snapshots for item in snapshot.weaknesses)
        learning_roadmap = self._top_items(
            (item for snapshot in snapshots for item in snapshot.next_focus),
            limit=6,
        )
        trend_summary = self._trend_summary(
            count=len(snapshots),
            public_dimensions=public_dimensions,
            strengths=strengths,
            weaknesses=weaknesses,
        )
        global_profile = GlobalProfileDocument(
            public_dimensions=public_dimensions,
            role_dimensions=role_dimensions,
            strengths=strengths,
            weaknesses=weaknesses,
            learning_roadmap=learning_roadmap,
            trend_summary=trend_summary,
        )
        markdown = self.render_global_profile_markdown(global_profile)
        self.profile_service.update_global_profile(global_profile)
        self.profile_service.update_global_profile_markdown(markdown)
        return CapabilityArtifacts(
            snapshot=snapshots[-1],
            global_profile=global_profile,
            global_profile_markdown=markdown,
        )

    def ensure_artifacts(self, interview_id: str) -> CapabilityArtifacts:
        snapshot = self.refresh_snapshot(interview_id)
        global_payload = self.refresh_global_profile()
        return CapabilityArtifacts(
            snapshot=snapshot,
            global_profile=global_payload.global_profile,
            global_profile_markdown=global_payload.global_profile_markdown,
        )

    def render_global_profile_markdown(self, document: GlobalProfileDocument) -> str:
        lines = [
            "# 全局画像",
            "",
            document.trend_summary,
            "",
            "## 公共能力维度",
            "",
            "| 维度 | 分数 |",
            "| --- | --- |",
        ]
        for name, score in document.public_dimensions.items():
            lines.append(f"| {name} | {score} |")
        lines.extend(["", "## 岗位维度", ""])
        for role_name, dimensions in document.role_dimensions.items():
            lines.append(f"### {role_name}")
            lines.append("")
            for name, score in dimensions.items():
                lines.append(f"- {name}: {score}")
            lines.append("")
        lines.extend(
            [
                "## 优势",
                "",
                *self._bullet_block(document.strengths),
                "",
                "## 待改进",
                "",
                *self._bullet_block(document.weaknesses),
                "",
                "## 学习路线",
                "",
                *self._bullet_block(document.learning_roadmap),
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def _load_or_build_snapshots(self) -> list[CapabilitySnapshotDocument]:
        snapshots: list[CapabilitySnapshotDocument] = []
        for item in self.repository.list_all():
            snapshot = self.repository.load_capability_snapshot(item.interview_id)
            if snapshot is None and self.repository.load_analyses(item.interview_id) is not None:
                snapshot = self.refresh_snapshot(item.interview_id)
            if snapshot is not None:
                snapshots.append(snapshot)
        snapshots.sort(key=lambda document: document.updated_at)
        return snapshots

    def _public_dimensions(self, analyses: list[TopicAnalysis]) -> dict[str, float]:
        if not analyses:
            return {}
        dimensions: dict[str, float] = {}
        for key, builder in PUBLIC_DIMENSION_BUILDERS.items():
            values = [builder(analysis) for analysis in analyses]
            dimensions[key] = round(sum(values) / len(values), 1)
        dimensions["overall"] = round(
            sum(analysis.rubric.weighted_total() for analysis in analyses) / len(analyses),
            1,
        )
        return dimensions

    def _role_dimensions(self, analyses: list[TopicAnalysis]) -> dict[str, float]:
        grouped: defaultdict[str, list[float]] = defaultdict(list)
        for analysis in analyses:
            grouped[analysis.question_understanding.question_type].append(analysis.rubric.weighted_total())
        return {
            key: round(sum(values) / len(values), 1)
            for key, values in grouped.items()
            if values
        }

    def _aggregate_public_dimensions(self, snapshots: list[CapabilitySnapshotDocument]) -> dict[str, float]:
        grouped: defaultdict[str, list[float]] = defaultdict(list)
        for snapshot in snapshots:
            for name, score in snapshot.public_dimensions.items():
                grouped[name].append(score)
        return {name: round(sum(values) / len(values), 1) for name, values in grouped.items()}

    def _aggregate_role_dimensions(
        self,
        snapshots: list[CapabilitySnapshotDocument],
        metas: dict[str, InterviewMetaDocument | None],
    ) -> dict[str, dict[str, float]]:
        grouped: defaultdict[str, defaultdict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for snapshot in snapshots:
            meta = metas.get(snapshot.interview_id)
            role_name = meta.target_position if meta and meta.target_position else "default"
            for name, score in snapshot.role_dimensions.items():
                grouped[role_name][name].append(score)
        result: dict[str, dict[str, float]] = {}
        for role_name, dimensions in grouped.items():
            result[role_name] = {
                dimension: round(sum(values) / len(values), 1)
                for dimension, values in dimensions.items()
            }
        return result

    def _snapshot_summary(
        self,
        *,
        public_dimensions: dict[str, float],
        strengths: list[str],
        weaknesses: list[str],
        meta: InterviewMetaDocument | None,
    ) -> str:
        best_dimension = max(public_dimensions, key=public_dimensions.get) if public_dimensions else None
        weakest_dimension = min(public_dimensions, key=public_dimensions.get) if public_dimensions else None
        target = meta.target_position if meta and meta.target_position else "当前目标岗位"
        return (
            f"{target} 方向下，本场表现最强的是 {best_dimension or 'overall'}，"
            f"当前主要短板集中在 {weakest_dimension or 'overall'}。"
            f"优势关键词：{self._join_brief(strengths)}；待改进关键词：{self._join_brief(weaknesses)}。"
        )

    def _trend_summary(
        self,
        *,
        count: int,
        public_dimensions: dict[str, float],
        strengths: list[str],
        weaknesses: list[str],
    ) -> str:
        best_dimension = max(public_dimensions, key=public_dimensions.get) if public_dimensions else "overall"
        weakest_dimension = min(public_dimensions, key=public_dimensions.get) if public_dimensions else "overall"
        return (
            f"已聚合 {count} 场面试。当前最稳定的能力维度是 {best_dimension}，"
            f"最需要持续补强的是 {weakest_dimension}。"
            f"高频优势：{self._join_brief(strengths)}；高频短板：{self._join_brief(weaknesses)}。"
        )

    def _next_focus(self, weaknesses: list[str]) -> list[str]:
        focus_map = {
            "回答细节不够充分": "补齐答案细节和例证",
            "缺少原理、取舍或量化细节": "强化原理、取舍与量化表达",
            "表达结构可以更清晰": "统一结构化表达模板",
            "与目标岗位的匹配表达不足": "提升岗位匹配度表达",
            "追问下的展开深度还不够": "增强追问承接能力",
            "回答偏短，证据不足": "增加案例、数字和结果支撑",
        }
        focus = [focus_map[item] for item in weaknesses if item in focus_map]
        return self._top_items(focus, limit=4)

    def _top_items(self, items, limit: int = 5) -> list[str]:
        counter = Counter(item.strip() for item in items if item and item.strip())
        return [item for item, _ in counter.most_common(limit)]

    def _join_brief(self, items: list[str]) -> str:
        return "、".join(items[:3]) if items else "暂无"

    def _bullet_block(self, items: list[str]) -> list[str]:
        return [f"- {item}" for item in items] or ["- 暂无"]
