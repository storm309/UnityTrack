from datetime import date

from app.data.synthetic import SyntheticDataSource


def test_generator_determinism() -> None:
    """Verify that same seed generates byte-for-byte identical datasets."""
    ds1 = SyntheticDataSource(seed=42)
    ds2 = SyntheticDataSource(seed=42)

    assert ds1.get_corridors() == ds2.get_corridors()
    assert ds1.get_sections() == ds2.get_sections()
    assert ds1.get_resources() == ds2.get_resources()
    assert ds1.get_train_slots() == ds2.get_train_slots()
    assert ds1.get_block_windows() == ds2.get_block_windows()
    assert ds1.get_tasks() == ds2.get_tasks()

    # Different seed should generate different task distribution
    ds3 = SyntheticDataSource(seed=99)
    assert ds1.get_tasks() != ds3.get_tasks()


def test_task_constraint_sanity() -> None:
    """Verify that all generated tasks satisfy operational railway constraints."""
    ds = SyntheticDataSource(seed=42)
    tasks = ds.get_tasks()

    assert len(tasks) == 50

    for t in tasks:
        # Feasibility: deadline must be >= earliest_start + duration
        assert t["deadline"] >= t["earliest_start"] + t["duration_min"], (
            f"Task {t['id']} has infeasible deadline {t['deadline']} < {t['earliest_start']} + {t['duration_min']}"
        )

        # Value bounds
        assert 1 <= t["criticality"] <= 5
        assert 1 <= t["defect_severity"] <= 5
        assert 0.0 <= t["traffic_impact"] <= 1.0
        assert t["crew_needed"] >= 1
        assert t["department"] in {"ENGINEERING", "TRACTION", "SNT"}


def test_block_windows_never_overlap_trains() -> None:
    """Verify mathematical guarantee: maintenance windows never conflict with train slots."""
    ds = SyntheticDataSource(seed=42)
    sections = ds.get_sections()

    for sec in sections:
        sec_id = sec["id"]
        trains = ds.get_train_slots(section_id=sec_id)
        windows = ds.get_block_windows(section_id=sec_id)

        assert len(windows) > 0, f"Section {sec_id} should have maintenance windows"

        for w in windows:
            w_start = w["start_min"]
            w_end = w["end_min"]
            assert w_end > w_start
            assert w["duration_min"] == w_end - w_start
            assert w["duration_min"] >= 90, "Windows must be at least 90 minutes"

            for tr in trains:
                t_start = tr["start_min"]
                t_end = tr["end_min"]

                # Overlap condition: max(w_start, t_start) < min(w_end, t_end)
                overlap = max(w_start, t_start) < min(w_end, t_end)
                assert not overlap, (
                    f"Conflict detected on section {sec_id}: "
                    f"Window [{w_start}, {w_end}] overlaps train {tr['train_no']} [{t_start}, {t_end}]"
                )


def test_realism_distribution() -> None:
    """Verify presence of overdue tasks, power-off tasks, and tight deadlines."""
    ds = SyntheticDataSource(seed=42)
    tasks = ds.get_tasks()
    today = date(2026, 10, 19)

    departments = {t["department"] for t in tasks}
    assert departments == {"ENGINEERING", "TRACTION", "SNT"}

    # Overdue tasks
    overdue_tasks = [t for t in tasks if date.fromisoformat(t["due_date"]) <= today]
    assert len(overdue_tasks) >= 5, "Synthetic data must contain overdue tasks"

    # Power off tasks (TRD)
    power_off_tasks = [t for t in tasks if t["requires_power_off"]]
    assert len(power_off_tasks) >= 10, "Synthetic data must contain tasks requiring power off"

    # Track block tasks (ENG)
    track_block_tasks = [t for t in tasks if t["requires_track_block"]]
    assert len(track_block_tasks) >= 15, "Synthetic data must contain tasks requiring track block"

    # Tight deadline tasks (deadline margin <= 180 min)
    tight_tasks = [
        t for t in tasks if (t["deadline"] - (t["earliest_start"] + t["duration_min"])) <= 180
    ]
    assert len(tight_tasks) >= 5, "Synthetic data must contain tight-deadline tasks"
