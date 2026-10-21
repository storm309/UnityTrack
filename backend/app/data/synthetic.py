import random
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.data.adapter import DataSource


class SyntheticDataSource(DataSource):
    """Generates deterministic synthetic Indian Railways maintenance data."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.horizon_days = 7
        self.horizon_minutes = self.horizon_days * 24 * 60  # 10,080 minutes
        self.base_date = date(2026, 10, 19)

        # Pre-generate datasets deterministically
        self._corridors: List[Dict[str, Any]] = []
        self._sections: List[Dict[str, Any]] = []
        self._resources: List[Dict[str, Any]] = []
        self._train_slots: List[Dict[str, Any]] = []
        self._block_windows: List[Dict[str, Any]] = []
        self._tasks: List[Dict[str, Any]] = []

        self._generate_all()

    def _generate_all(self) -> None:
        self._generate_corridors_and_sections()
        self._generate_resources()
        self._generate_train_timetable()
        self._derive_block_windows()
        self._generate_tasks()

    def _generate_corridors_and_sections(self) -> None:
        corridor_id = "CORR-01"
        self._corridors = [
            {
                "id": corridor_id,
                "name": "Northern Corridor (New Delhi - Kanpur Central)",
            }
        ]

        section_specs = [
            ("SEC-01", "New Delhi - Ghaziabad (NDLS-GZB)", 0.0, 25.6),
            ("SEC-02", "Ghaziabad - Aligarh (GZB-ALJN)", 25.6, 131.0),
            ("SEC-03", "Aligarh - Tundla (ALJN-TDL)", 131.0, 209.4),
            ("SEC-04", "Tundla - Firozabad (TDL-FZD)", 209.4, 226.2),
            ("SEC-05", "Firozabad - Shikohabad (FZD-SKB)", 226.2, 246.0),
            ("SEC-06", "Shikohabad - Etawah (SKB-ETW)", 246.0, 300.5),
            ("SEC-07", "Etawah - Phaphund (ETW-PHD)", 300.5, 383.2),
            ("SEC-08", "Phaphund - Kanpur Central (PHD-CNB)", 383.2, 440.0),
        ]

        self._sections = []
        for idx, (sec_id, name, km_start, km_end) in enumerate(section_specs):
            self._sections.append(
                {
                    "id": sec_id,
                    "corridor_id": corridor_id,
                    "name": name,
                    "km_start": km_start,
                    "km_end": km_end,
                    "order_index": idx,
                }
            )

    def _generate_resources(self) -> None:
        self._resources = [
            {
                "id": "RES-ENG",
                "department": "ENGINEERING",
                "capacity_per_window": 4,  # Max 4 civil engineering crews concurrently
            },
            {
                "id": "RES-TRD",
                "department": "TRACTION",
                "capacity_per_window": 2,  # Max 2 OHE wiring/tower wagon crews concurrently
            },
            {
                "id": "RES-SNT",
                "department": "SNT",
                "capacity_per_window": 3,  # Max 3 signaling teams concurrently
            },
        ]

    def _generate_train_timetable(self) -> None:
        """Generate realistic train timetables across 7 days for all sections."""
        self._train_slots = []
        corridor_id = "CORR-01"

        # Daily train definitions: (train_no, base_departure_min_in_day, transit_per_section_min, priority)
        # 1440 min per day.
        # Night lull: 00:30 (min 30) to 04:30 (min 270) -> NO passenger or freight departures.
        # Midday lull: 11:30 (min 690) to 13:30 (min 810) -> NO departures.
        train_definitions = [
            ("12004-Shatabdi", 360, 25, 1),  # 06:00
            ("22436-VandeBharat", 480, 20, 1),  # 08:00
            ("04152-KanpurExp", 580, 35, 3),  # 09:40
            ("12398-Mahabodhi", 830, 25, 2),  # 13:50
            ("12424-Rajdhani", 980, 22, 1),  # 16:20
            ("12566-BiharSK", 1120, 28, 2),  # 18:40
            ("12802-Purushottam", 1260, 26, 2),  # 21:00
            ("BOXN-88-Freight", 280, 35, 4),  # 04:40 (Freight right after night window)
            ("BCN-52-Freight", 1380, 35, 4),  # 23:00 (Freight right before night window)
        ]

        slot_counter = 1
        for day in range(self.horizon_days):
            day_offset = day * 1440
            for train_no, dep_min, transit_min, priority in train_definitions:
                for sec_idx, section in enumerate(self._sections):
                    # Progression along corridor
                    sec_start = day_offset + dep_min + (sec_idx * (transit_min + 5))
                    sec_end = sec_start + transit_min
                    if sec_end <= self.horizon_minutes:
                        self._train_slots.append(
                            {
                                "id": f"TS-{slot_counter:04d}",
                                "corridor_id": corridor_id,
                                "section_id": section["id"],
                                "train_no": f"{train_no}-D{day + 1}",
                                "start_min": sec_start,
                                "end_min": sec_end,
                                "priority": priority,
                            }
                        )
                        slot_counter += 1

    def _derive_block_windows(self) -> None:
        """Derive allowable maintenance block windows from timetable gaps."""
        self._block_windows = []
        window_counter = 1
        min_window_duration = 90  # Railway blocks need at least 90 minutes to be effective

        for section in self._sections:
            sec_id = section["id"]
            # Get train slots on this section sorted chronologically
            slots = [s for s in self._train_slots if s["section_id"] == sec_id]
            slots.sort(key=lambda x: x["start_min"])

            # Find gaps between consecutive train slots
            gaps: List[tuple[int, int]] = []
            current_time = 0

            for slot in slots:
                if slot["start_min"] > current_time:
                    gap_duration = slot["start_min"] - current_time
                    if gap_duration >= min_window_duration:
                        gaps.append((current_time, slot["start_min"]))
                current_time = max(current_time, slot["end_min"])

            # Check gap after last train until horizon end
            if current_time < self.horizon_minutes:
                if (self.horizon_minutes - current_time) >= min_window_duration:
                    gaps.append((current_time, self.horizon_minutes))

            for start_min, end_min in gaps:
                duration = end_min - start_min
                # Determine if center of window is during night hours (22:00 to 06:00)
                mid_min = (start_min + end_min) // 2
                minute_of_day = mid_min % 1440
                is_night = (minute_of_day >= 1320) or (minute_of_day <= 360)

                self._block_windows.append(
                    {
                        "id": f"BW-{window_counter:04d}",
                        "section_id": sec_id,
                        "start_min": start_min,
                        "end_min": end_min,
                        "duration_min": duration,
                        "is_night_window": is_night,
                    }
                )
                window_counter += 1

    def _generate_tasks(self) -> None:
        """Generate exactly 50 realistic tasks across 3 railway departments."""
        self._tasks = []

        # Specifications for realistic departmental maintenance tasks
        eng_task_templates = [
            ("Track Tamping & Lining", "Ballast", 180, 4, 3, 0.45, 3),
            ("Rail Weld Ultrasonic Defect Repair", "Rails", 120, 5, 5, 0.85, 2),
            ("Sleeper Renewal & Fastener Tightening", "Sleepers", 240, 3, 3, 0.35, 4),
            ("Turnout Frog & Switch Blade Replacement", "Turnout", 240, 5, 4, 0.75, 4),
            ("Deep Screening & Ballast Cleaning", "Ballast", 240, 4, 3, 0.60, 4),
            ("Glued Insulated Rail Joint Overhaul", "Fishplates", 120, 3, 2, 0.30, 2),
            ("Switch Expansion Joint (SEJ) Adjustment", "Rails", 150, 4, 4, 0.50, 3),
        ]

        trd_task_templates = [
            ("OHE Contact Wire Splicing & Replacement", "OHE Contact Wire", 180, 5, 5, 0.80, 2),
            ("Bracket Insulator High-Pressure Washing", "Insulator", 120, 3, 3, 0.25, 2),
            ("Auto-Tensioning Device (ATD) Calibration", "ATD", 90, 4, 3, 0.40, 2),
            ("Neutral Section Inspection & Overhaul", "Neutral Section", 150, 5, 4, 0.70, 2),
            ("Cantilever Assembly Periodic Overhaul", "Catenary", 120, 3, 2, 0.35, 2),
            ("Dropper Replacement & Stagger Adjustment", "OHE Contact Wire", 120, 4, 3, 0.45, 2),
        ]

        snt_task_templates = [
            ("Electric Point Machine Overhaul & Lubrication", "Point Machine", 90, 4, 4, 0.65, 2),
            ("Track Circuit Lead & Impedance Bond Testing", "Track Circuit", 60, 3, 3, 0.20, 2),
            (
                "Digital Axle Counter (DAC) Sensor Reset & Calibration",
                "Axle Counter",
                90,
                5,
                5,
                0.85,
                2,
            ),
            (
                "Multi-Aspect Color Light Signal Unit Replacement",
                "Signal Aspect",
                120,
                4,
                3,
                0.50,
                3,
            ),
            (
                "Solid State Interlocking (SSI) Relay Rack Maintenance",
                "Interlocking Relay",
                150,
                5,
                4,
                0.60,
                2,
            ),
            ("Audio Frequency Track Circuit (AFTC) Tuning", "Track Circuit", 90, 4, 3, 0.35, 2),
        ]

        task_id_counter = 1

        # We will generate: 20 ENG, 15 TRD, 15 SNT = 50 tasks
        dept_configs = [
            (
                "ENGINEERING",
                eng_task_templates,
                20,
                False,
                True,
            ),  # No power off, track block required
            ("TRACTION", trd_task_templates, 15, True, False),  # Power off required, no track block
            ("SNT", snt_task_templates, 15, False, False),  # Co-locatable with both TRD & ENG
        ]

        for dept, templates, count, req_power, req_track in dept_configs:
            for i in range(count):
                template = templates[i % len(templates)]
                sec_idx = (task_id_counter - 1) % len(self._sections)
                sec_id = self._sections[sec_idx]["id"]

                title_base, asset_type, base_dur, crit, sev, traffic_imp, crew = template

                # Adjust duration with rng
                dur_variation = self.rng.choice([0, 15, 30, -15])
                duration = max(60, min(240, base_dur + dur_variation))

                # Earliest start distributed across days 0 to 4
                earliest_day = (task_id_counter * 3) % 5
                earliest_start = earliest_day * 1440 + (self.rng.randint(0, 10) * 60)

                # Tight vs standard vs relaxed deadlines
                # Tasks can have a tight deadline (<= 180 min margin) if an immediate permissible window exists
                sec_windows = [
                    w for w in self._block_windows
                    if w["section_id"] == sec_id and w["duration_min"] >= duration
                ]
                has_immediate_window = any(
                    (min(w["end_min"], earliest_start + duration + 180) - max(w["start_min"], earliest_start)) >= duration
                    for w in sec_windows
                )

                if has_immediate_window and (i % 3 == 0 or task_id_counter in [1, 5, 9, 13, 21, 29, 37]) and task_id_counter != 48:
                    # Tight deadline
                    deadline = earliest_start + duration + 180
                elif i % 2 == 1:
                    # Moderate deadline (spans 24-48h)
                    deadline = min(self.horizon_minutes, earliest_start + duration + 1440)
                else:
                    # Relaxed deadline (spans 48-72h)
                    deadline = min(
                        self.horizon_minutes,
                        earliest_start + duration + self.rng.choice([2880, 3600, 4320]),
                    )

                # Ensure deadline sanity
                if deadline < earliest_start + duration:
                    deadline = earliest_start + duration + 120

                # Realism: Some tasks are overdue
                # Days offset for due_date
                if task_id_counter in [1, 5, 12, 18, 25, 33, 41, 48]:
                    # Overdue: due date was before horizon start or on day 0
                    days_overdue = 1 + (task_id_counter % 5)
                    due_d = self.base_date - timedelta(days=days_overdue)
                    last_d = due_d - timedelta(days=90)
                else:
                    # Future due date
                    days_ahead = 2 + (task_id_counter % 6)
                    due_d = self.base_date + timedelta(days=days_ahead)
                    last_d = due_d - timedelta(days=60)

                # Criticality & Defect severity variations
                crit_val = max(1, min(5, crit + self.rng.choice([-1, 0, 1])))
                sev_val = max(1, min(5, sev + self.rng.choice([-1, 0, 1])))
                traffic_val = round(
                    max(0.1, min(0.95, traffic_imp + self.rng.choice([-0.05, 0.0, 0.05]))), 2
                )

                self._tasks.append(
                    {
                        "id": f"TASK-{task_id_counter:03d}",
                        "department": dept,
                        "section_id": sec_id,
                        "title": f"[{dept[:3]}] {title_base} ({sec_id})",
                        "asset_type": asset_type,
                        "duration_min": duration,
                        "earliest_start": earliest_start,
                        "deadline": deadline,
                        "criticality": crit_val,
                        "defect_severity": sev_val,
                        "last_done_date": last_d.isoformat(),
                        "due_date": due_d.isoformat(),
                        "traffic_impact": traffic_val,
                        "crew_needed": crew,
                        "requires_power_off": req_power,
                        "requires_track_block": req_track,
                        "status": "PENDING",
                    }
                )
                task_id_counter += 1

    # DataSource implementation methods
    def get_corridors(self) -> List[Dict[str, Any]]:
        return list(self._corridors)

    def get_sections(self, corridor_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if corridor_id:
            return [s for s in self._sections if s["corridor_id"] == corridor_id]
        return list(self._sections)

    def get_tasks(
        self,
        department: Optional[str] = None,
        section_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        res = self._tasks
        if department:
            res = [t for t in res if t["department"] == department]
        if section_id:
            res = [t for t in res if t["section_id"] == section_id]
        if status:
            res = [t for t in res if t["status"] == status]
        return list(res)

    def get_train_slots(
        self,
        corridor_id: Optional[str] = None,
        section_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        res = self._train_slots
        if corridor_id:
            res = [s for s in res if s["corridor_id"] == corridor_id]
        if section_id:
            res = [s for s in res if s["section_id"] == section_id]
        return list(res)

    def get_resources(self) -> List[Dict[str, Any]]:
        return list(self._resources)

    def get_block_windows(
        self,
        section_id: Optional[str] = None,
        is_night_window: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        res = self._block_windows
        if section_id:
            res = [w for w in res if w["section_id"] == section_id]
        if is_night_window is not None:
            res = [w for w in res if w["is_night_window"] == is_night_window]
        return list(res)
