import argparse
import logging

from sqlalchemy.orm import Session

from app.data.synthetic import SyntheticDataSource
from app.database import Base, SessionLocal, engine
from app.models.domain import (
    BlockWindow,
    Corridor,
    Plan,
    PlannedBlock,
    Resource,
    Scenario,
    Section,
    Task,
    TrainSlot,
)

logger = logging.getLogger("unitytrack.seed")


def seed_database(db: Session, seed: int = 42, reset: bool = True) -> dict[str, int]:
    """Seed the database with deterministic synthetic railway data."""
    if reset:
        logger.info("Resetting existing domain tables...")
        # Clear in reverse dependency order
        db.query(PlannedBlock).delete()
        db.query(Scenario).delete()
        db.query(Plan).delete()
        db.query(Task).delete()
        db.query(TrainSlot).delete()
        db.query(BlockWindow).delete()
        db.query(Section).delete()
        db.query(Corridor).delete()
        db.query(Resource).delete()
        db.commit()

    source = SyntheticDataSource(seed=seed)

    # 1. Corridors
    corridors_data = source.get_corridors()
    for c in corridors_data:
        db.add(Corridor(**c))
    db.commit()

    # 2. Sections
    sections_data = source.get_sections()
    for s in sections_data:
        db.add(Section(**s))
    db.commit()

    # 3. Resources
    resources_data = source.get_resources()
    for r in resources_data:
        db.add(Resource(**r))
    db.commit()

    # 4. Train Slots
    trains_data = source.get_train_slots()
    for t in trains_data:
        db.add(TrainSlot(**t))
    db.commit()

    # 5. Block Windows
    windows_data = source.get_block_windows()
    for w in windows_data:
        db.add(BlockWindow(**w))
    db.commit()

    # 6. Tasks
    tasks_data = source.get_tasks()
    for t in tasks_data:
        db.add(Task(**t))
    db.commit()

    summary = {
        "corridors": len(corridors_data),
        "sections": len(sections_data),
        "resources": len(resources_data),
        "train_slots": len(trains_data),
        "block_windows": len(windows_data),
        "tasks": len(tasks_data),
    }

    logger.info("Seeding completed successfully: %s", summary)
    return summary


def main() -> None:
    """CLI entry point for python -m app.seed."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Seed UnityTrack database with synthetic data")
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for determinism (default: 42)"
    )
    parser.add_argument(
        "--no-reset", action="store_true", help="Do not clear existing data before seeding"
    )
    args = parser.parse_args()

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        summary = seed_database(db, seed=args.seed, reset=not args.no_reset)
        print("Database seeded successfully:")
        for table, count in summary.items():
            print(f"  - {table}: {count} records")
    finally:
        db.close()


if __name__ == "__main__":
    main()
