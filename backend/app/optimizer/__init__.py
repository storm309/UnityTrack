"""UnityTrack Optimizer Package.

Independent optimization package with NO dependencies on FastAPI or the database.
All data structures are pure Python / Pydantic models.
"""

from app.optimizer.baseline import BaselinePlanResult, schedule_siloed_baseline
from app.optimizer.bundling import (
    CONFLICT_CORRIDOR_MISMATCH,
    CONFLICT_CREW_CAPACITY_EXCEEDED,
    CONFLICT_SAFETY_LIVE_LINE,
    CONFLICT_SECTION_MISMATCH,
    CONFLICT_SECTION_NOT_ADJACENT,
    CONFLICT_WINDOW_DISJOINT,
    CONFLICT_WINDOW_TOO_SHORT,
    BundleCandidate,
    BundlingConfig,
    CompatibilityResult,
    SectionInfo,
    TaskItem,
    check_pairwise_compatibility,
    compute_bundle_metrics,
    find_candidate_bundles,
)
from app.optimizer.priority import (
    BAND_CRITICAL,
    BAND_HIGH,
    BAND_LOW,
    BAND_MEDIUM,
    FactorContributions,
    PriorityResult,
    PriorityWeights,
    calculate_task_priority,
    compute_overdue_ratio,
    determine_priority_band,
    rank_tasks_by_priority,
)
from app.optimizer.scheduler import (
    OptimizerPlanResult,
    SchedulerConfig,
    solve_maintenance_schedule,
)
from app.optimizer.validator import (
    ScheduledBlock,
    ScheduledTaskAssignment,
    ValidationResult,
    validate_schedule,
)

__all__ = [
    # Priority engine
    "PriorityWeights",
    "FactorContributions",
    "PriorityResult",
    "BAND_CRITICAL",
    "BAND_HIGH",
    "BAND_MEDIUM",
    "BAND_LOW",
    "determine_priority_band",
    "compute_overdue_ratio",
    "calculate_task_priority",
    "rank_tasks_by_priority",
    # Bundling engine
    "TaskItem",
    "SectionInfo",
    "BundlingConfig",
    "CompatibilityResult",
    "BundleCandidate",
    "CONFLICT_CORRIDOR_MISMATCH",
    "CONFLICT_SECTION_MISMATCH",
    "CONFLICT_SECTION_NOT_ADJACENT",
    "CONFLICT_WINDOW_DISJOINT",
    "CONFLICT_WINDOW_TOO_SHORT",
    "CONFLICT_CREW_CAPACITY_EXCEEDED",
    "CONFLICT_SAFETY_LIVE_LINE",
    "check_pairwise_compatibility",
    "compute_bundle_metrics",
    "find_candidate_bundles",
    # Scheduler engine
    "SchedulerConfig",
    "OptimizerPlanResult",
    "solve_maintenance_schedule",
    # Validator engine
    "ScheduledBlock",
    "ScheduledTaskAssignment",
    "ValidationResult",
    "validate_schedule",
    # Baseline scheduler
    "BaselinePlanResult",
    "schedule_siloed_baseline",
]
