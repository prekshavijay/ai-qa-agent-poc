"""Story-text heuristics for requirement analysis.

These helpers read only the words in the story. They do not add actors,
business rules, metrics, or quality attributes that the story does not state.
"""

import re
from typing import List, Sequence, Tuple

VAGUE_TERMS: Tuple[str, ...] = (
    "user-friendly",
    "user friendly",
    "easy to use",
    "to be determined",
    "and so on",
    "as needed",
    "intuitive",
    "seamless",
    "robust",
    "efficient",
    "properly",
    "quickly",
    "quick",
    "fast",
    "slow",
    "modern",
    "smooth",
    "responsive",
    "adequate",
    "optimal",
    "simple",
    "easy",
    "tbd",
    "etc",
)

NFR_KEYWORDS = {
    "performance": (
        "performance",
        "response time",
        "latency",
        "throughput",
        "load time",
        "fast",
        "quickly",
        "quick",
        "slow",
    ),
    "security": (
        "secure",
        "security",
        "encrypt",
        "encryption",
        "unauthorized",
        "authentication",
        "authorization",
        "https",
        "audit",
    ),
    "usability": (
        "usability",
        "user-friendly",
        "user friendly",
        "intuitive",
        "accessible",
        "accessibility",
        "wcag",
        "easy to use",
    ),
    "reliability": ("reliability", "uptime", "availability"),
    "scalability": ("scalability", "concurrent users", "scale to"),
}

_BEHAVIOR_PATTERN = re.compile(
    r"\b("
    r"request|requests|requested|submit|submits|submitted|send|sends|sent|"
    r"view|views|viewed|create|creates|created|update|updates|updated|"
    r"delete|deletes|deleted|display|displays|displayed|show|shows|"
    r"enter|enters|entered|select|selects|selected|save|saves|saved|"
    r"cancel|cancels|search|searches|filter|filters|notify|notifies|"
    r"expire|expires|expired|contain|contains|validate|validates|"
    r"reject|rejects|allow|allows|prevent|prevents|store|stores|"
    r"receive|receives|redirect|redirects|login|log|reset|set|sets|"
    r"load|loads|loaded|appear|appears|calculate|calculates|"
    r"upload|uploads|download|downloads|export|exports|import|imports"
    r")\b",
    re.IGNORECASE,
)

_MEASUREMENT_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:"
    r"ms|milliseconds?|seconds?|secs?|minutes?|mins?|hours?|"
    r"%|percent|users|requests|characters?|chars|digits"
    r")\b",
    re.IGNORECASE,
)

_ACTOR_PATTERN = re.compile(
    r"\b("
    r"user|users|admin|admins|customer|customers|system|visitor|visitors|"
    r"operator|operators|manager|managers|member|members|guest|guests"
    r")\b",
    re.IGNORECASE,
)

_GWT_PATTERN = re.compile(r"\b(given|when|then)\b", re.IGNORECASE)

MISSING_DESCRIPTION_QUESTION = (
    "What user or system behavior should the story description cover?"
)
MISSING_ACCEPTANCE_CRITERIA_QUESTION = (
    "What acceptance criteria define done for this story?"
)
MISSING_ACTOR_QUESTION = "Who is the primary actor for this story?"


def normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


def split_sentences(text: str) -> List[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _contains_term(text: str, term: str) -> bool:
    return re.search(r"\b" + re.escape(term) + r"\b", text, re.IGNORECASE) is not None


def find_vague_terms(text: str) -> List[str]:
    found: List[str] = []
    for term in sorted(VAGUE_TERMS, key=len, reverse=True):
        if _contains_term(text, term):
            found.append(term)
    return found


def supported_categories(text: str) -> List[str]:
    categories: List[str] = []
    for category, keywords in NFR_KEYWORDS.items():
        if any(_contains_term(text, keyword) for keyword in keywords):
            categories.append(category)
    return categories


def has_behavior(text: str) -> bool:
    return _BEHAVIOR_PATTERN.search(text) is not None


def has_measurement(text: str) -> bool:
    return _MEASUREMENT_PATTERN.search(text) is not None


def has_actor(text: str) -> bool:
    return _ACTOR_PATTERN.search(text) is not None


def is_concrete(text: str) -> bool:
    return has_behavior(text) or has_measurement(text) or _GWT_PATTERN.search(text) is not None


def classify_testability(text: str) -> str:
    """Return testable, partially_testable, or not_testable for one statement."""
    vague = find_vague_terms(text)
    concrete = is_concrete(text)
    if vague and concrete:
        return "partially_testable"
    if vague:
        return "not_testable"
    return "testable"


def is_quality_only(text: str) -> bool:
    """True when the sentence states a quality attribute and no behavior."""
    return bool(supported_categories(text)) and not has_behavior(text) and not has_measurement(text)


def story_corpus(title: str, description: str, acceptance_criteria: Sequence[str]) -> str:
    parts = [title, description, *acceptance_criteria]
    return "\n".join(part for part in parts if part and part.strip())


def is_grounded(statement: str, corpus: str) -> bool:
    """True when the statement is copied from the story, not paraphrased into new scope."""
    normalized_statement = normalize_text(statement)
    normalized_corpus = normalize_text(corpus)
    if not normalized_statement or not normalized_corpus:
        return False
    return normalized_statement in normalized_corpus


def build_story_summary(title: str, description: str) -> str:
    clean_title = title.strip()
    clean_description = description.strip()
    if not clean_description:
        return (
            f"'{clean_title}' does not include a description, "
            "so no behavior can be summarized from the story body."
        )
    first = split_sentences(clean_description)[0]
    if normalize_text(first) == normalize_text(clean_title):
        return first
    return f"{clean_title}: {first}"


def ambiguity_question(statement: str) -> str:
    return f'What measurable outcome replaces the vague statement: "{statement}"?'


def build_clarification_questions(
    *,
    title: str,
    description: str,
    acceptance_criteria: Sequence[str],
    ambiguous_statements: Sequence[str],
) -> List[str]:
    questions: List[str] = []
    if not description.strip():
        questions.append(MISSING_DESCRIPTION_QUESTION)
    if not acceptance_criteria:
        questions.append(MISSING_ACCEPTANCE_CRITERIA_QUESTION)
    corpus = story_corpus(title, description, acceptance_criteria)
    if not has_actor(corpus):
        questions.append(MISSING_ACTOR_QUESTION)
    for statement in ambiguous_statements:
        questions.append(ambiguity_question(statement))
    return questions


def determine_analysis_status(
    *,
    description: str,
    acceptance_criteria: Sequence[str],
    title: str,
    ambiguity_count: int,
    testability_statuses: Sequence[str],
) -> str:
    if not description.strip():
        return "insufficient_input"
    corpus = story_corpus(title, description, acceptance_criteria)
    actor_missing = not has_actor(corpus)
    if (
        ambiguity_count
        or not acceptance_criteria
        or actor_missing
        or not testability_statuses
        or any(status != "testable" for status in testability_statuses)
    ):
        return "needs_clarification"
    return "complete"
