"""Pure Python Priority Scoring Engine for Railway Maintenance Tasks.

Strict decoupling guarantee: This module has NO dependencies on FastAPI or SQLAlchemy.
It operates purely on standard Python data structures and types.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Union


@dataclass(frozen=True)
class PriorityWeights:
    """Configurable weights for the multi-factor priority scoring formula."""

    criticality: float = 0.35
    defect_severity: float = 0.30
    overdue_ratio: float = 0.20
    traffic_impact: float = 0.15

    def validate(self) -> None:
        """Validate that all weights are non-negative and sum to 1.0."""
        weights = [self.criticality, self.defect_severity, self.overdue_ratio, self.traffic_impact]
        for w in weights:
            if w < 0.0:
                raise ValueError(f"Priority weight cannot be negative: {w}")
        total = sum(weights)
        if abs(total - 1.0) > 1e-5:
            raise ValueError(f"Priority weights must sum to 1.0 (got {total:.5f})")


@dataclass(frozen=True)
class FactorContributions:
    """Individual point contributions of each factor towards the total 0-100 score."""

    criticality: float
    defect_severity: float
    overdue_ratio: float
    traffic_impact: float


@dataclass
class PriorityResult:
    """Scored task result containing 0-100 score, rank, priority band, and breakdown."""

    task_id: str
    score: float
    rank: int
    priority_band: str
    contributions: FactorContributions
    factors_normalized: Dict[str, float]


# Documented priority band thresholds
BAND_CRITICAL = "CRITICAL"  # >= 75.0
BAND_HIGH = "HIGH"  # >= 50.0 and < 75.0
BAND_MEDIUM = "MEDIUM"  # >= 25.0 and < 50.0
BAND_LOW = "LOW"  # < 25.0


def determine_priority_band(score: float) -> str:
    """Determine the priority band based on documented thresholds.

    - CRITICAL: score >= 75.0 (Immediate attention required)
    - HIGH:     50.0 <= score < 75.0 (Urgent planned maintenance)
    - MEDIUM:   25.0 <= score < 50.0 (Routine maintenance window)
    - LOW:      score < 25.0 (Opportunistic / low impact)
    """
    if score >= 75.0:
        return BAND_CRITICAL
    if score >= 50.0:
        return BAND_HIGH
    if score >= 25.0:
        return BAND_MEDIUM
    return BAND_LOW


def parse_date(d: Union[str, date]) -> date:
    """Parse date object or ISO date string."""
    if isinstance(d, date):
        return d
    return date.fromisoformat(d.strip())


def compute_overdue_ratio(
    today: Union[str, date],
    due_date: Union[str, date],
    last_done_date: Optional[Union[str, date]] = None,
    default_interval_days: int = 30,
) -> float:
    """Calculate overdue ratio: clamp((today - due_date) / max(interval, 1), 0, 1).

    Definition:
    - If today <= due_date: Task is not overdue -> overdue_ratio = 0.0.
    - If today > due_date: Task is overdue by (today - due_date).days.
    - interval = (due_date - last_done_date).days if last_done_date is provided and valid,
      otherwise default_interval_days (default: 30 days).
    - The ratio is clamped to [0.0, 1.0].
    """
    today_dt = parse_date(today)
    due_dt = parse_date(due_date)

    if today_dt <= due_dt:
        return 0.0

    days_overdue = (today_dt - due_dt).days

    interval = default_interval_days
    if last_done_date is not None:
        last_dt = parse_date(last_done_date)
        calc_interval = (due_dt - last_dt).days
        if calc_interval > 0:
            interval = calc_interval

    ratio = days_overdue / max(interval, 1)
    return max(0.0, min(1.0, float(ratio)))


def normalize_1_to_5(val: int) -> float:
    """Normalize integer 1-5 scale linearly to 0.0-1.0: (val - 1) / 4.0."""
    clamped = max(1, min(5, val))
    return (clamped - 1) / 4.0


def calculate_task_priority(
    task: Dict[str, Any],
    weights: Optional[PriorityWeights] = None,
    today: Optional[Union[str, date]] = None,
    rank: int = 1,
) -> PriorityResult:
    """Calculate the explainable priority score and factor breakdown for a single task."""
    if weights is None:
        weights = PriorityWeights()
    weights.validate()

    today_dt = parse_date(today) if today is not None else date(2026, 10, 19)

    # 1. Normalize Criticality: 1-5 -> 0.0 to 1.0
    crit_val = int(task.get("criticality", 3))
    crit_norm = normalize_1_to_5(crit_val)

    # 2. Normalize Defect Severity: 1-5 -> 0.0 to 1.0
    sev_val = int(task.get("defect_severity", 3))
    sev_norm = normalize_1_to_5(sev_val)

    # 3. Compute Overdue Ratio: 0.0 to 1.0
    due_str = task.get("due_date", today_dt.isoformat())
    last_done_str = task.get("last_done_date")
    overdue_ratio = compute_overdue_ratio(
        today=today_dt,
        due_date=due_str,
        last_done_date=last_done_str,
    )

    # 4. Traffic Impact: Already 0.0 to 1.0
    traffic_impact = float(task.get("traffic_impact", 0.5))
    traffic_impact = max(0.0, min(1.0, traffic_impact))

    # Factor contributions (0 to 100 points scale)
    c_crit = 100.0 * weights.criticality * crit_norm
    c_sev = 100.0 * weights.defect_severity * sev_norm
    c_overdue = 100.0 * weights.overdue_ratio * overdue_ratio
    c_traffic = 100.0 * weights.traffic_impact * traffic_impact

    # Total score 0 - 100
    raw_score = c_crit + c_sev + c_overdue + c_traffic
    score = round(max(0.0, min(100.0, raw_score)), 2)

    priority_band = determine_priority_band(score)

    contributions = FactorContributions(
        criticality=round(c_crit, 2),
        defect_severity=round(c_sev, 2),
        overdue_ratio=round(c_overdue, 2),
        traffic_impact=round(c_traffic, 2),
    )

    factors_normalized = {
        "criticality_norm": round(crit_norm, 4),
        "severity_norm": round(sev_norm, 4),
        "overdue_ratio": round(overdue_ratio, 4),
        "traffic_impact": round(traffic_impact, 4),
    }

    return PriorityResult(
        task_id=str(task.get("id", "UNKNOWN")),
        score=score,
        rank=rank,
        priority_band=priority_band,
        contributions=contributions,
        factors_normalized=factors_normalized,
    )


def rank_tasks_by_priority(
    tasks: List[Dict[str, Any]],
    weights: Optional[PriorityWeights] = None,
    today: Optional[Union[str, date]] = None,
) -> List[PriorityResult]:
    """Score all tasks and return them ranked by priority score in descending order."""
    if weights is None:
        weights = PriorityWeights()
    weights.validate()

    scored = [calculate_task_priority(t, weights=weights, today=today) for t in tasks]

    # Stable sorting: primary by score desc, secondary by deadline asc, tertiary by task_id asc
    task_lookup = {t["id"]: t for t in tasks}

    def sort_key(item: PriorityResult) -> tuple[float, int, str]:
        raw_t = task_lookup.get(item.task_id, {})
        deadline = raw_t.get("deadline", 999999)
        return (-item.score, deadline, item.task_id)

    scored.sort(key=sort_key)

    # Assign sequential ranks 1, 2, 3...
    ranked_results: List[PriorityResult] = []
    for rank_idx, item in enumerate(scored, start=1):
        item.rank = rank_idx
        ranked_results.append(item)

    return ranked_results
