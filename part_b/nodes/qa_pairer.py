from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from config import get_settings
from part_b.llm_utils import safe_invoke_json_model
from part_b.prompts.phase3 import QA_EXTRACTOR_SYSTEM_PROMPT, build_qa_extractor_prompt
from part_b.schemas import (
    DialogueTurn,
    InterviewMetaDocument,
    QaPairsDocument,
    SpeakerRole,
    TopicGroup,
    TranscriptionDocument,
)


VALID_TOPIC_TYPES = {"technical", "project", "behavioral", "hr", "other"}

# Chinese filler words commonly found in ASR transcripts
NOISE_TURNS = {
    "\u55ef",  # 嗯 (en/uh)
    "\u554a",  # 啊 (ah)
    "\u54e6",  # 哦 (oh)
    "\u597d\u7684",  # 好的 (okay)
    "\u884c",  # 行 (okay/sure)
    "\u53ef\u4ee5",  # 可以 (okay/can)
    "\u6536\u5230",  # 收到 (received)
    "\u662f\u7684",  # 是的 (yes)
    "\u5bf9",  # 对 (correct)
    "\u597d",  # 好 (good/okay)
}

# Low-value question patterns to filter out (English and Chinese)
LOW_VALUE_QUESTION_HINTS = (
    "can you hear",
    "camera",
    "thesis",
    "graduation",
    "join",
    "salary",
    "team size",
    "bye",
    "\u542c\u89c1",  # 听见 (can you hear)
    "\u542c\u5230",  # 听到 (can you hear)
    "\u6444\u50cf\u5934",  # 摄像头 (camera)
    "\u5f00\u59cb\u5427",  # 开始吧 (let's start)
    "\u8bba\u6587",  # 论文 (thesis)
    "\u7b54\u8fa9",  # 答辩 (defense)
    "\u6bd5\u4e1a",  # 毕业 (graduation)
    "\u5165\u804c",  # 入职 (join)
    "\u85aa\u8d44",  # 薪资 (salary)
    "\u5de5\u8d44",  # 工资 (salary)
    "\u8f6c\u6b63",  # 转正 (conversion to full-time)
    "\u56e2\u961f",  # 团队 (team)
    "\u591a\u5c11\u4eba",  # 多少人 (how many people)
    "\u62dc\u62dc",  # 拜拜 (bye)
    "\u52a0\u73ed",  # 加班 (overtime)
    "\u5b9e\u4e60\u662f\u5427",  # 实习是吧 (internship, right?)
    "\u5230\u5c97",  # 到岗 (start date)
)

# Question indicators (English and Chinese)
QUESTION_HINTS = (
    "?",
    "\uff1f",  # ？ (Chinese question mark)
    "why",
    "how",
    "introduce",
    "explain",
    "difference",
    "design",
    "optimize",
    "\u4e3a\u4ec0\u4e48",  # 为什么 (why)
    "\u600e\u4e48",  # 怎么 (how)
    "\u5982\u4f55",  # 如何 (how)
    "\u4ecb\u7ecd",  # 介绍 (introduce)
    "\u804a\u804a",  # 聊聊 (chat about)
    "\u8bb2\u8bb2",  # 讲讲 (tell about)
    "\u533a\u522b",  # 区别 (difference)
    "\u7406\u89e3",  # 理解 (understand)
    "\u8bbe\u8ba1",  # 设计 (design)
    "\u4f18\u5316",  # 优化 (optimize)
    "\u54ea\u4e9b\u7b56\u7565",  # 哪些策略 (which strategies)
    "\u4e3a\u4ec0\u4e48\u9009",  # 为什么选 (why choose)
    "\u5c55\u5f00\u8bf4",  # 展开说 (elaborate)
    "\u8be6\u7ec6\u8bf4",  # 详细说 (explain in detail)
    "\u6838\u5fc3\u533a\u522b",  # 核心区别 (core difference)
)

MAX_QA_TOPICS = 12

# ASR homophone corrections for technical terms (regex patterns)
TECH_TERM_REGEX_REPLACEMENTS = (
    (re.compile(r"\blong\s*cha\b", flags=re.IGNORECASE), "LangChain"),
    (re.compile(r"\blong\s*gra(?:ph|ve)?\b", flags=re.IGNORECASE), "LangGraph"),
    (re.compile(r"\bcloud\s*code\b", flags=re.IGNORECASE), "Cloud Code"),
    (re.compile(r"\bvs\s*code\b", flags=re.IGNORECASE), "VS Code"),
    (re.compile(r"\bagent\s+teams\b", flags=re.IGNORECASE), "Agent Teams"),
)

# Chinese ASR homophone replacements for technical terms (literal replacements)
TECH_TERM_LITERAL_REPLACEMENTS = {
    "A 站": "Agent",  # Common ASR error
    "A 进": "Agent",  # Common ASR error
}


class QaPairDraft(BaseModel):
    qa_id: int
    question_turn_ids: list[str] = Field(default_factory=list)
    answer_turn_ids: list[str] = Field(default_factory=list)
    question: str
    answer: str = ""
    topic_type: Literal["technical", "project", "behavioral", "hr", "other"] = "other"


class QaExtractionBatch(BaseModel):
    qa_pairs: list[QaPairDraft] = Field(default_factory=list)


def build_qa_pairs(
    document: TranscriptionDocument,
    *,
    meta: InterviewMetaDocument | None = None,
) -> QaPairsDocument:
    turns = _normalize_turns(document)
    topics = _build_llm_topics(turns) or _build_fallback_topics(turns)
    return QaPairsDocument(interview_id=document.interview_id, topics=topics)


def _normalize_turns(document: TranscriptionDocument) -> list[DialogueTurn]:
    raw_turns: list[DialogueTurn] = []
    for index, segment in enumerate(document.segments, start=1):
        text = _clean_text(segment.text)
        if not text or _is_noise_turn(text):
            continue
        raw_turns.append(
            DialogueTurn(
                turn_id=f"seg_{segment.segment_id or index}",
                speaker_id=segment.speaker_id,
                role=segment.role,
                text=text,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                source_segment_ids=[segment.segment_id],
            )
        )

    merged = _merge_consecutive_turns(raw_turns)
    return [turn.model_copy(update={"turn_id": f"t{index}"}) for index, turn in enumerate(merged, start=1)]


def _build_llm_topics(turns: list[DialogueTurn]) -> list[TopicGroup] | None:
    if not turns:
        return []

    settings = get_settings()
    qa_batch = safe_invoke_json_model(
        QaExtractionBatch,
        system_prompt=QA_EXTRACTOR_SYSTEM_PROMPT,
        user_prompt=build_qa_extractor_prompt(transcript_lines=[_turn_line(turn) for turn in turns]),
        temperature=0.1,
        max_tokens=6000,
        model_name=settings.llm_structured_model,
        json_mode=True,
        retries=2,
    )
    if qa_batch is None or not qa_batch.qa_pairs:
        return None

    turn_map = {turn.turn_id: turn for turn in turns if turn.turn_id}
    turn_index = {turn.turn_id: index for index, turn in enumerate(turns) if turn.turn_id}
    seen_keys: set[tuple[str, ...] | str] = set()
    materialized: list[tuple[int, TopicGroup]] = []

    for draft in qa_batch.qa_pairs:
        question_turns = _select_turns(turn_map, draft.question_turn_ids, SpeakerRole.interviewer)
        answer_turns = _select_turns(turn_map, draft.answer_turn_ids, SpeakerRole.candidate)
        question_text = _normalize_question_text(draft.question, question_turns)
        answer_text = _normalize_answer_text(draft.answer, answer_turns)

        if not question_text or not answer_text:
            continue
        if _should_drop_question(question_text):
            continue

        dedupe_key = tuple(turn.turn_id for turn in question_turns if turn.turn_id) or _normalize_key(question_text)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        exchanges = _sorted_unique_turns(question_turns + answer_turns, turn_index)
        if not exchanges:
            exchanges = _build_synthetic_turns(question_text=question_text, answer_text=answer_text)

        order_candidates = [turn_index.get(turn.turn_id, 10**9) for turn in exchanges if turn.turn_id]
        order_key = min(order_candidates) if order_candidates else len(materialized)
        topic_type = _normalize_topic_type(draft.topic_type, question_text, answer_text)
        materialized.append(
            (
                order_key,
                TopicGroup(
                    topic_id=0,
                    main_question=question_text,
                    question_text=question_text,
                    question_turn_ids=[turn.turn_id for turn in question_turns if turn.turn_id],
                    answer_text=answer_text,
                    answer_turn_ids=[turn.turn_id for turn in answer_turns if turn.turn_id],
                    followups=[],
                    turn_ids=[turn.turn_id for turn in exchanges if turn.turn_id],
                    topic_summary=_topic_summary(question_text, answer_text),
                    topic_type=topic_type,
                    exchange_count=len(exchanges),
                    has_followup=False,
                    boundary_confidence=0.95,
                    split_reason=["llm_transcript_reviewable_qas"],
                    exchanges=exchanges,
                ),
            )
        )

    if not materialized:
        return None

    topics: list[TopicGroup] = []
    for index, (_, topic) in enumerate(sorted(materialized, key=lambda item: item[0]), start=1):
        topics.append(topic.model_copy(update={"topic_id": index}))
        if len(topics) >= MAX_QA_TOPICS:
            break
    return topics or None


def _build_fallback_topics(turns: list[DialogueTurn]) -> list[TopicGroup]:
    topics: list[TopicGroup] = []
    index = 0

    while index < len(turns):
        turn = turns[index]
        if turn.role != SpeakerRole.interviewer or not _is_question_like(turn.text) or _should_drop_question(turn.text):
            index += 1
            continue

        question_turns = [turn]
        pointer = index + 1
        while pointer < len(turns) and turns[pointer].role == SpeakerRole.interviewer and _is_question_like(turns[pointer].text):
            if not _should_drop_question(turns[pointer].text):
                question_turns.append(turns[pointer])
            pointer += 1

        answer_turns: list[DialogueTurn] = []
        while pointer < len(turns) and turns[pointer].role != SpeakerRole.interviewer:
            if turns[pointer].role == SpeakerRole.candidate:
                answer_turns.append(turns[pointer])
            pointer += 1

        question_text = _normalize_question_text(_join_turn_text(question_turns), question_turns)
        answer_text = _normalize_answer_text("", answer_turns)
        if question_text and answer_text and not _should_drop_question(question_text):
            topics.append(
                TopicGroup(
                    topic_id=len(topics) + 1,
                    main_question=question_text,
                    question_text=question_text,
                    question_turn_ids=[item.turn_id for item in question_turns if item.turn_id],
                    answer_text=answer_text,
                    answer_turn_ids=[item.turn_id for item in answer_turns if item.turn_id],
                    followups=[],
                    turn_ids=[item.turn_id for item in question_turns + answer_turns if item.turn_id],
                    topic_summary=_topic_summary(question_text, answer_text),
                    topic_type=_normalize_topic_type("other", question_text, answer_text),
                    exchange_count=len(question_turns) + len(answer_turns),
                    has_followup=False,
                    boundary_confidence=0.55,
                    split_reason=["fallback_direct_question_answer"],
                    exchanges=question_turns + answer_turns,
                )
            )
            if len(topics) >= MAX_QA_TOPICS:
                break

        index = max(pointer, index + 1)

    return topics


def _merge_consecutive_turns(turns: list[DialogueTurn]) -> list[DialogueTurn]:
    merged: list[DialogueTurn] = []
    for turn in turns:
        if merged and _can_merge_turns(merged[-1], turn):
            previous = merged[-1]
            merged[-1] = previous.model_copy(
                update={
                    "text": _join_text([previous.text, turn.text]),
                    "end_ms": turn.end_ms or previous.end_ms,
                    "source_segment_ids": previous.source_segment_ids + turn.source_segment_ids,
                }
            )
            continue
        merged.append(turn)
    return merged


def _can_merge_turns(previous: DialogueTurn, current: DialogueTurn) -> bool:
    if previous.speaker_id != current.speaker_id or previous.role != current.role:
        return False
    if previous.end_ms is None or current.start_ms is None:
        return True
    return current.start_ms - previous.end_ms <= 12_000


def _select_turns(
    turn_map: dict[str, DialogueTurn],
    turn_ids: list[str],
    role: SpeakerRole,
) -> list[DialogueTurn]:
    selected: list[DialogueTurn] = []
    seen: set[str] = set()
    for turn_id in turn_ids:
        if turn_id in seen:
            continue
        turn = turn_map.get(turn_id)
        if turn is None or turn.role != role:
            continue
        selected.append(turn)
        seen.add(turn_id)
    return selected


def _normalize_question_text(draft_question: str, question_turns: list[DialogueTurn]) -> str:
    candidate = _clean_sentence(draft_question)
    if not candidate or _looks_like_generated_summary(candidate):
        candidate = _clean_sentence(_join_turn_text(question_turns))
    return candidate


def _normalize_answer_text(draft_answer: str, answer_turns: list[DialogueTurn]) -> str:
    candidate = _clean_sentence(draft_answer)
    if len(candidate) < 12:
        candidate = _clean_sentence(_join_turn_text(answer_turns))
    return candidate


def _normalize_topic_type(topic_type: str, question_text: str, answer_text: str) -> str:
    if topic_type in VALID_TOPIC_TYPES:
        return topic_type
    combined = f"{question_text}\n{answer_text}".lower()
    # Chinese keywords for topic classification
    if any(token in combined for token in ("\u9879\u76ee", "\u8d1f\u8d23", "\u843d\u5730", "\u534f\u4f5c", "agent", "rag")):  # 项目，负责，落地，协作
        return "project"
    if any(token in combined for token in ("\u4e3a\u4ec0\u4e48", "\u51b2\u7a81", "\u79bb\u804c", "\u89c4\u5212", "\u4f18\u70b9", "\u7f3a\u70b9", "\u52a8\u673a")):  # 为什么，冲突，离职，规划，优点，缺点，动机
        return "behavioral"
    if any(token in combined for token in ("redis", "mysql", "langgraph", "langchain", "\u5411\u91cf", "\u53ec\u56de", "\u56fe\u72b6\u6001\u673a")):  # 向量，召回，图状态机
        return "technical"
    return "other"


def _build_synthetic_turns(*, question_text: str, answer_text: str) -> list[DialogueTurn]:
    return [
        DialogueTurn(turn_id=None, speaker_id="interviewer", role=SpeakerRole.interviewer, text=question_text),
        DialogueTurn(turn_id=None, speaker_id="candidate", role=SpeakerRole.candidate, text=answer_text),
    ]


def _sorted_unique_turns(turns: list[DialogueTurn], turn_index: dict[str, int]) -> list[DialogueTurn]:
    deduped: dict[str, DialogueTurn] = {}
    synthetic: list[DialogueTurn] = []
    for turn in turns:
        if turn.turn_id:
            deduped.setdefault(turn.turn_id, turn)
        else:
            synthetic.append(turn)
    ordered = sorted(deduped.values(), key=lambda item: turn_index.get(item.turn_id, 10**9))
    return ordered + synthetic


def _turn_line(turn: DialogueTurn) -> str:
    return f"{turn.turn_id or 't?'} | {turn.role.value} | {turn.text}"


def _clean_text(text: str) -> str:
    cleaned = " ".join(text.replace("\r", " ").replace("\n", " ").split()).strip()
    return _normalize_tech_terms(cleaned)


def _clean_sentence(text: str) -> str:
    cleaned = _clean_text(text)
    cleaned = re.sub(r"^(um|uh|well|so)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" ,.;:\u3002\uff0c\uff1b")


def _join_turn_text(turns: list[DialogueTurn]) -> str:
    return _join_text([turn.text for turn in turns if turn.text.strip()])


def _join_text(parts: list[str]) -> str:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    return "\n".join(cleaned)


def _is_noise_turn(text: str) -> bool:
    cleaned = text.strip().lower()
    return cleaned in NOISE_TURNS or len(cleaned) <= 1


def _is_question_like(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in QUESTION_HINTS)


def _should_drop_question(text: str) -> bool:
    lowered = text.lower()
    if _looks_like_generated_summary(lowered):
        return True
    return any(hint in lowered for hint in LOW_VALUE_QUESTION_HINTS)


def _looks_like_generated_summary(text: str) -> bool:
    lowered = text.lower()
    return (
        lowered.startswith("\u5019\u9009\u4eba")  # 候选人
        or lowered.startswith("\u9762\u8bd5\u4e2d")  # 面试中
        or lowered.startswith("\u9762\u8bd5\u5b98\u5bf9\u5019\u9009\u4eba")  # 面试官对候选人
        or "\u63d0\u5230\u4e86\u54ea\u4e9b" in lowered  # 提到了哪些
    )


def _normalize_key(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _topic_summary(question_text: str, answer_text: str) -> str:
    question = question_text.strip()
    if len(question) <= 48:
        return question
    if answer_text:
        answer = answer_text.strip().replace("\n", " ")
        if answer:
            return answer[:48] + ("..." if len(answer) > 48 else "")
    return question[:48] + "..."


def _normalize_tech_terms(text: str) -> str:
    normalized = text
    for old, new in TECH_TERM_LITERAL_REPLACEMENTS.items():
        normalized = normalized.replace(old, new)
    for pattern, replacement in TECH_TERM_REGEX_REPLACEMENTS:
        normalized = pattern.sub(replacement, normalized)
    return normalized
