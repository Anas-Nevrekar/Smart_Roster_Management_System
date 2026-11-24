"""Safely and idempotently seed one development database from bundled fixtures."""
from __future__ import annotations

import argparse
from collections import Counter
from getpass import getpass
import sys

from app.core.config import Settings
from app.core.database import DatabaseConnectionManager
from app.repositories.memory import map_fixture
from app.repositories.mongodb import COLLECTION_NAMES, MongoRepository
from app.scheduling_engine.sample_data_fixed import get_dataset

RESET_DATABASES = {"smart_roster_dev", "smart_roster_conflict_test", "smart_roster_test"}
SEED_COLLECTIONS = {
    "employees": "employees",
    "pods": "pods",
    "brands": "brands",
    "processes": "processes",
    "eligibility": "eligibility",
    "operating_rules": "operating_rules",
    "time_off": "time_off",
    "public_holidays": "public_holidays",
}


def _verify_relationships(snapshot: dict[str, list[dict]]) -> None:
    employees = {row["employee_id"] for row in snapshot["employees"]}
    pods = {row["pod_id"] for row in snapshot["pods"]}
    brands = {row["brand_id"] for row in snapshot["brands"]}
    processes = {row["process_id"] for row in snapshot["processes"]}
    problems = []
    for employee in snapshot["employees"]:
        if employee.get("pod_id") and employee["pod_id"] not in pods:
            problems.append(f"employee {employee['employee_id']} references a missing pod")
    for pod in snapshot["pods"]:
        if pod.get("pod_lead_id") and pod["pod_lead_id"] not in employees:
            problems.append(f"pod {pod['pod_id']} references a missing employee lead")
    for collection in ("eligibility", "operating_rules"):
        for row in snapshot[collection]:
            if collection == "eligibility" and row["employee_id"] not in employees:
                problems.append(f"{collection} record {row['id']} references a missing employee")
            if row["brand_id"] not in brands or row["process_id"] not in processes:
                problems.append(f"{collection} record {row['id']} references a missing brand or process")
    for row in snapshot["time_off"]:
        if row["employee_id"] not in employees:
            problems.append(f"time-off record {row['id']} references a missing employee")
    if problems:
        raise RuntimeError("Fixture relationship verification failed: " + "; ".join(problems[:10]))


def _counts(repository: MongoRepository) -> dict[str, int]:
    database = repository.manager.require_database()
    return {logical: database[COLLECTION_NAMES[logical]].count_documents({}) for logical in SEED_COLLECTIONS}


def _run(args) -> int:
    settings = Settings()
    database_name = args.database or settings.mongodb_database
    if args.scenario == "conflict" and database_name != "smart_roster_conflict_test":
        print("Refusing to seed the conflict fixture outside smart_roster_conflict_test.", file=sys.stderr)
        return 2
    if args.scenario == "valid" and database_name == "smart_roster_conflict_test":
        print("Refusing to seed valid data into the conflict-test database.", file=sys.stderr)
        return 2
    if args.reset:
        if database_name not in RESET_DATABASES:
            print("Reset is restricted to the named development/test databases.", file=sys.stderr)
            return 2
        print(f"WARNING: --reset permanently deletes all Smart Roster data in {database_name}.")
        if getpass(f"Type {database_name} to confirm reset: ") != database_name:
            print("Reset cancelled.")
            return 2

    manager = DatabaseConnectionManager(settings.mongodb_uri, database_name)
    if not manager.connect():
        print("MongoDB connection failed. Configure MONGODB_URI and verify Atlas network access and database permissions.", file=sys.stderr)
        return 1
    repository = MongoRepository(manager)
    try:
        database = manager.require_database()
        if args.reset:
            for mongo_collection in COLLECTION_NAMES.values():
                database[mongo_collection].delete_many({})

        mapped = map_fixture(get_dataset(args.scenario))
        actions: Counter[str] = Counter()
        for logical, source_name in SEED_COLLECTIONS.items():
            for record in mapped[source_name]:
                actions[repository.upsert_seed_record(logical, record)] += 1

        _verify_relationships(repository.snapshot())
        counts = _counts(repository)
        active_employees = sum(item["is_active"] for item in repository.list("employees"))
        print("MongoDB sample data seeding complete")
        print(f"Database:             {database_name}")
        print(f"Scenario:             {args.scenario}")
        print(f"Employees:            {counts['employees']} (active: {active_employees})")
        for logical, label in (("pods", "Pods"), ("brands", "Brands"), ("processes", "Processes"),
                               ("eligibility", "Eligibility"), ("operating_rules", "Operating rules"),
                               ("time_off", "Time off"), ("public_holidays", "Public holidays")):
            print(f"{label + ':':22}{counts[logical]}")
        print(f"Fixture rows inserted/updated/unchanged: {actions['inserted']}/{actions['updated']}/{actions['unchanged']}")
        print("All relationships verified. Unique indexes verified.")
        return 0
    finally:
        manager.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("valid", "conflict"), default="valid")
    parser.add_argument("--database", help="Override MONGODB_DATABASE; conflict fixtures require smart_roster_conflict_test.")
    parser.add_argument("--reset", action="store_true", help="Explicitly clear a named development/test database before seeding.")
    return _run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
