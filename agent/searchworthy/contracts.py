"""Typed knowledge contracts. IDs and lifecycle belong to the program, not the LLM."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import json
import re
import unicodedata


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def identity(kind, value):
    return kind + '-' + hashlib.sha256(canonical(value).encode()).hexdigest()[:16]


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC', str(text)).split()).casefold()


class Truth(str, Enum):
    TRUE = 'TRUE'
    FALSE = 'FALSE'
    UNKNOWN = 'UNKNOWN'
    CONFLICT = 'CONFLICT'


def conjunction(values):
    values = [Truth(v) for v in values]
    if Truth.FALSE in values:
        return Truth.FALSE
    if Truth.CONFLICT in values:
        return Truth.CONFLICT
    if Truth.UNKNOWN in values:
        return Truth.UNKNOWN
    return Truth.TRUE


def condition_tree(tree, conditions):
    if isinstance(tree, str):
        return Truth(conditions[tree].truth)
    if 'all' in tree:
        return conjunction(condition_tree(t, conditions) for t in tree['all'])
    if 'any' in tree:
        vals = [condition_tree(t, conditions) for t in tree['any']]
        if Truth.TRUE in vals:
            return Truth.TRUE
        if Truth.CONFLICT in vals:
            return Truth.CONFLICT
        if Truth.UNKNOWN in vals:
            return Truth.UNKNOWN
        return Truth.FALSE
    if 'not' in tree:
        val = condition_tree(tree['not'], conditions)
        return {Truth.TRUE: Truth.FALSE, Truth.FALSE: Truth.TRUE}.get(val, val)
    raise ValueError('condition tree requires all/any/not or a condition key')


@dataclass
class Citation:
    document: str
    quote: str


@dataclass
class CaseFact:
    id: str
    entity: str
    predicate: str
    value: object
    unit: str
    scope: dict
    citations: list[dict]


@dataclass
class Requirement:
    id: str
    entities: list[str]
    predicate: str
    object: str
    scope: dict
    question: str
    route: str
    fact_ids: list[str]
    targets: list[str] = field(default_factory=list)
    status: str = 'OPEN'
    query: str = ''
    priority: float = 1.0
    searches: int = 0
    no_progress: int = 0
    history: list[dict] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    certificate: dict | None = None
    pending_reads: list[str] = field(default_factory=list)
    uncertainty: dict | None = None
    review_epoch: int = 0


@dataclass
class Condition:
    key: str
    proposition: str
    truth: str
    citations: list[dict]
    route: str = 'PUBLIC'
    dependencies: list[str] = field(default_factory=list)
    subjects: list[str] | None = None
    subject_scope: dict | None = None


def condition_identity(app, condition):
    """The fact's subjects may differ from the actions receiving its effects."""
    subjects = app.entities if condition.subjects is None else condition.subjects
    scope = app.scope if condition.subject_scope is None else condition.subject_scope
    return identity('condition-world', [sorted(subjects), scope,
                                      normalized(condition.proposition)])


@dataclass
class Rule:
    id: str
    key: str
    version: str
    text: str
    kind: str
    citations: list[dict]
    condition: object
    exception: object | None = None
    replaces: list[str] = field(default_factory=list)
    status: str = 'OBSERVED'
    condition_definitions: dict[str, str] = field(default_factory=dict)
    interpretation_id: str | None = None
    corrects_interpretation_id: str | None = None


@dataclass
class Application:
    id: str
    rule_id: str
    entities: list[str]
    conditions: dict[str, Condition]
    contribution_ids: list[str]
    requirement_ids: list[str]
    status: str = 'UNKNOWN'
    reviewed_version: int = 0
    scope: dict = field(default_factory=dict)


@dataclass
class ModelContribution:
    id: str
    key: str
    source_kind: str
    source_id: str
    kind: str
    payload: dict
    citations: list[dict]
    dependencies: list[str] = field(default_factory=list)
    replaces: list[str] = field(default_factory=list)
    active: bool = True


@dataclass
class DecisionRecord:
    snapshot_id: str | None
    solve_status: str
    knowledge_status: str
    recommendation: dict | None
    recommendation_conditions: list[dict]
    unresolved: list[dict]
    stop_reason: str
    scope: str
    resources: dict
    error: dict | None = None


def encode(value):
    if hasattr(value, '__dataclass_fields__'):
        return asdict(value)
    raise TypeError(type(value).__name__)
