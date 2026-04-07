import re
from dataclasses import dataclass
from typing import Optional


_RELATIONSHIP_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bwife\b", "wife"),
    (r"\bhusband\b", "husband"),
    (r"\bspouse\b", "spouse"),
    (r"\bpartner\b", "partner"),
    (r"\bboyfriend\b", "boyfriend"),
    (r"\bboy\s+friend\b", "boyfriend"),
    (r"\bgirlfriend\b", "girlfriend"),
    (r"\bgirl\s+friend\b", "girlfriend"),
    (r"\bparents\b", "parents"),
    (r"\bmother\b", "mother"),
    (r"\bmom\b", "mom"),
    (r"\bmum\b", "mum"),
    (r"\bfather\b", "father"),
    (r"\bdad\b", "dad"),
    (r"\bsiblings\b", "siblings"),
    (r"\bsister\b", "sister"),
    (r"\bbrother\b", "brother"),
    (r"\bfriends\b", "friends"),
    (r"\bfriend\b", "friend"),
    (r"\bfamily\b", "family"),
    (r"\bchildren\b", "children"),
    (r"\bkids\b", "kids"),
    (r"\bdaughter\b", "daughter"),
    (r"\bson\b", "son"),
)

_SECRECY_PATTERNS: tuple[str, ...] = (
    r"\bnot aware\b",
    r"\bunaware\b",
    r"\bdoesn'?t know\b",
    r"\bdon'?t know\b",
    r"\bhaven'?t told\b",
    r"\bhave not told\b",
    r"\bhaven'?t mentioned\b",
    r"\bnever told\b",
    r"\bhiding\b",
    r"\bkeeping it from\b",
    r"\bkeeping it secret\b",
    r"\bkeeping this from\b",
    r"\bkeeping this secret\b",
    r"\bno idea about\b",
    r"\bwithout.*knowing\b",
    r"\bnot know about\b",
)

_CONCERN_PATTERNS: tuple[str, ...] = (
    r"\bworried\b",
    r"\bconcerned\b",
    r"\bafraid\b",
    r"\bscared\b",
    r"\bconcern\b",
)

_CONFLICT_PATTERNS: tuple[str, ...] = (
    r"\bhate\b",
    r"\bhates\b",
    r"\bhating\b",
    r"\bangry\b",
    r"\bmad\b",
    r"\bupset\b",
    r"\bjudg(e|ing|ed)\b",
    r"\bdisapprov(e|es|ing|ed)\b",
    r"\bcriticis(e|es|ing|ed)\b",
    r"\bcriticiz(e|es|ing|ed)\b",
    r"\bdisappointed\b",
    r"\bashamed of me\b",
    r"\bblam(e|es|ing|ed)\b",
)

_SUPPORT_PATTERNS: tuple[str, ...] = (
    r"\bsupport(s|ive)?\b",
    r"\bhas my back\b",
    r"\bshow(s|ing)? up for me\b",
    r"\btrying to help\b",
    r"\bthere for me\b",
)

_CLAUSE_SPLIT_RE = re.compile(r"(?:[.;!?]|\bbut\b|\bbecause\b|\bwhile\b|\balthough\b)", re.IGNORECASE)


@dataclass(frozen=True)
class RelationshipClauseAnalysis:
    mentions: list[str]
    canonical_mentions: list[str]
    primary_mention: Optional[str]
    tone: Optional[str]
    evidence: Optional[str]
    clause_text: str

    @property
    def has_relationship(self) -> bool:
        return bool(self.mentions)


@dataclass(frozen=True)
class RecoveryClauseAnalysis:
    theme: Optional[str]
    evidence: Optional[str]
    clause_text: str


_CHANGE_READINESS_PATTERNS: tuple[str, ...] = (
    r"\bwant to stop\b",
    r"\bwant to quit\b",
    r"\bwant to change\b",
    r"\bneed to stop\b",
    r"\bneed to quit\b",
    r"\bready to stop\b",
    r"\bready to quit\b",
    r"\btrying to stop\b",
    r"\btrying to quit\b",
    r"\btrying to change\b",
    r"\bi want help\b",
    r"\bi want to get better\b",
)

_LAPSE_PATTERNS: tuple[str, ...] = (
    r"\brelaps(e|ed|ing)\b",
    r"\bslip(ped)?\b",
    r"\bused again\b",
    r"\bdrank again\b",
    r"\bhad a drink\b",
    r"\bsmoked again\b",
    r"\bgambled again\b",
    r"\bwent back to\b",
)

_SHAME_PATTERNS: tuple[str, ...] = (
    r"\bashamed\b",
    r"\bembarrassed\b",
    r"\bhate myself\b",
    r"\bdisgusted with myself\b",
    r"\bguilty\b",
    r"\bhumiliated\b",
    r"\bdisappointed in myself\b",
)

_PRESSURE_PATTERNS: tuple[str, ...] = (
    r"\bpressured\b",
    r"\bpushed\b",
    r"\bforced\b",
    r"\bcornered\b",
    r"\bnagging\b",
    r"\beveryone expects\b",
    r"\bpeople expect\b",
    r"\bbeing watched\b",
    r"\btold me to\b",
    r"\bkeep(s)? telling me\b",
    r"\bputting pressure on me\b",
)


def _iter_relationship_matches(message: str):
    msg_lc = (message or "").lower()
    for pattern, canonical in _RELATIONSHIP_PATTERNS:
        for match in re.finditer(pattern, msg_lc):
            yield match.start(), match.end(), match.group(0), canonical


def _find_clause_text(message: str, start: int, end: int) -> str:
    text = message or ""
    if not text:
        return ""

    boundaries = [0]
    for match in _CLAUSE_SPLIT_RE.finditer(text):
        boundaries.append(match.end())
    boundaries.append(len(text))

    clause_start = 0
    clause_end = len(text)
    for left, right in zip(boundaries, boundaries[1:]):
        if left <= start < right or left < end <= right:
            clause_start = left
            clause_end = right
            break
    return text[clause_start:clause_end].strip(" ,.;!?\n\t")


def _tone_from_text(text: str) -> tuple[Optional[str], Optional[str]]:
    for tone, patterns in (
        ("secrecy", _SECRECY_PATTERNS),
        ("conflict", _CONFLICT_PATTERNS),
        ("support", _SUPPORT_PATTERNS),
        ("concern", _CONCERN_PATTERNS),
    ):
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return tone, match.group(0)
    return None, None


def analyze_relationship_clause(message: str) -> RelationshipClauseAnalysis:
    msg = message or ""
    matches = sorted(_iter_relationship_matches(msg), key=lambda item: item[0])
    if not matches:
        return RelationshipClauseAnalysis([], [], None, None, None, "")

    mentions: list[str] = []
    canonical_mentions: list[str] = []
    primary_clause = ""
    tone: Optional[str] = None
    evidence: Optional[str] = None

    for index, (start, end, exact, canonical) in enumerate(matches):
        if exact not in mentions:
            mentions.append(exact)
        if canonical not in canonical_mentions:
            canonical_mentions.append(canonical)

        clause_text = _find_clause_text(msg, start, end)
        if index == 0:
            primary_clause = clause_text

        if tone is None:
            local_tone, local_evidence = _tone_from_text(clause_text.lower())
            if local_tone:
                tone = local_tone
                evidence = local_evidence

    if tone is None:
        msg_tone, msg_evidence = _tone_from_text(msg.lower())
        tone = msg_tone or "presence"
        evidence = msg_evidence

    return RelationshipClauseAnalysis(
        mentions=mentions,
        canonical_mentions=canonical_mentions,
        primary_mention=mentions[0],
        tone=tone,
        evidence=evidence,
        clause_text=primary_clause,
    )


def analyze_recovery_clause(message: str) -> RecoveryClauseAnalysis:
    msg = message or ""
    if not msg:
        return RecoveryClauseAnalysis(None, None, "")

    clauses = [
        chunk.strip(" ,.;!?\n\t")
        for chunk in _CLAUSE_SPLIT_RE.split(msg)
        if chunk and chunk.strip(" ,.;!?\n\t")
    ]
    if not clauses:
        clauses = [msg.strip()]

    for clause in clauses:
        clause_lc = clause.lower()
        for theme, patterns in (
            ("shame", _SHAME_PATTERNS),
            ("lapse", _LAPSE_PATTERNS),
            ("pressure", _PRESSURE_PATTERNS),
            ("change_readiness", _CHANGE_READINESS_PATTERNS),
        ):
            for pattern in patterns:
                match = re.search(pattern, clause_lc)
                if match:
                    return RecoveryClauseAnalysis(theme, match.group(0), clause)

    msg_lc = msg.lower()
    for theme, patterns in (
        ("shame", _SHAME_PATTERNS),
        ("lapse", _LAPSE_PATTERNS),
        ("pressure", _PRESSURE_PATTERNS),
        ("change_readiness", _CHANGE_READINESS_PATTERNS),
    ):
        for pattern in patterns:
            match = re.search(pattern, msg_lc)
            if match:
                return RecoveryClauseAnalysis(theme, match.group(0), msg.strip())

    return RecoveryClauseAnalysis(None, None, "")