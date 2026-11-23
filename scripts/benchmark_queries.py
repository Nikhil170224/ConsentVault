"""Benchmark key queries with EXPLAIN (ANALYZE, BUFFERS), before/after indexing.

Measures the /consents/check query and each report query. Only measured
numbers are reported. Results are printed and saved to docs/benchmarks.md.

Usage:
    python scripts/benchmark_queries.py [--database-url URL]
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

CHECK_SQL = """
SELECT c.id FROM consents c
JOIN purposes p ON p.id = c.purpose_id
WHERE p.organization_id = :org_id AND p.code = :code
  AND c.data_subject_id = :subject_id AND c.status = 'GRANTED'
  AND (c.expires_at IS NULL OR c.expires_at > NOW())
LIMIT 1
"""

INDEXES = {
    "ix_bench_consents_subject_purpose_status": "CREATE INDEX IF NOT EXISTS ix_bench_consents_subject_purpose_status ON consents (data_subject_id, purpose_id, status)",
    "ix_bench_events_org_type_created": "CREATE INDEX IF NOT EXISTS ix_bench_events_org_type_created ON consent_events (organization_id, event_type, created_at)",
    "ix_bench_dsr_org_status_due": "CREATE INDEX IF NOT EXISTS ix_bench_dsr_org_status_due ON dsr_requests (organization_id, status, due_date)",
}


def explain_ms(conn, sql: str, params: dict) -> tuple[float, str]:
    rows = conn.execute(text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {sql}"), params).fetchall()
    plan = "\n".join(r[0] for r in rows)
    match = re.search(r"Execution Time:\s*([\d.]+)\s*ms", plan)
    return (float(match.group(1)) if match else -1.0), plan


def wall_ms(conn, sql: str, params: dict, runs: int = 5) -> float:
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        conn.execute(text(sql), params).fetchall()
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    return times[len(times) // 2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark ConsentVault queries")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "postgresql+psycopg://consentvault:consentvault@localhost:5432/consentvault"),
    )
    args = parser.parse_args()
    sql_dir = Path(__file__).resolve().parents[1] / "app" / "sql"
    engine = create_engine(args.database_url)
    results: list[dict] = []

    with engine.connect() as conn:
        org_row = conn.execute(text("SELECT id FROM organizations LIMIT 1")).fetchone()
        if org_row is None:
            print("No data found. Run scripts/seed_data.py first.")
            return
        org_id = str(org_row[0])
        subj_row = conn.execute(
            text("SELECT id FROM data_subjects WHERE organization_id = :o LIMIT 1"), {"o": org_id}
        ).fetchone()
        subject_id = str(subj_row[0]) if subj_row else org_id
        counts = {
            t: conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            for t in ("data_subjects", "consents", "consent_events", "dsr_requests")
        }
        print("Row counts:", counts)

        queries = {
            "consent_check": (CHECK_SQL, {"org_id": org_id, "code": "marketing", "subject_id": subject_id}),
            "report_consent_rates": ((sql_dir / "consent_rates.sql").read_text(), {"org_id": org_id}),
            "report_withdrawal_trends": ((sql_dir / "withdrawal_trends.sql").read_text(), {"org_id": org_id}),
            "report_dsr_sla": ((sql_dir / "dsr_sla.sql").read_text(), {"org_id": org_id}),
        }

        # BEFORE: drop benchmark indexes, measure.
        for name in INDEXES:
            conn.execute(text(f"DROP INDEX IF EXISTS {name}"))
        conn.commit()
        before = {}
        for qname, (sql, params) in queries.items():
            ms, _ = explain_ms(conn, sql, params)
            before[qname] = (ms, wall_ms(conn, sql, params))

        # AFTER: create indexes, ANALYZE, measure again.
        for ddl in INDEXES.values():
            conn.execute(text(ddl))
        conn.execute(text("ANALYZE consents, consent_events, dsr_requests, purposes"))
        conn.commit()
        after = {}
        for qname, (sql, params) in queries.items():
            ms, _ = explain_ms(conn, sql, params)
            after[qname] = (ms, wall_ms(conn, sql, params))

    for qname in queries:
        results.append({
            "query": qname,
            "before_explain_ms": before[qname][0], "before_wall_ms": before[qname][1],
            "after_explain_ms": after[qname][0], "after_wall_ms": after[qname][1],
        })

    header = "| Query | Before EXPLAIN (ms) | Before wall median (ms) | After EXPLAIN (ms) | After wall median (ms) |"
    sep = "|---|---|---|---|---|"
    lines = [
        "# ConsentVault Benchmarks", "",
        "Measured with `EXPLAIN (ANALYZE, BUFFERS)` and median wall-clock of 5 runs.",
        "Only measured numbers are reported — rerun `scripts/benchmark_queries.py` to reproduce.", "",
        f"Row counts at benchmark time: {counts}", "",
        header, sep,
    ]
    for r in results:
        lines.append(
            f"| {r['query']} | {r['before_explain_ms']:.3f} | {r['before_wall_ms']:.3f} "
            f"| {r['after_explain_ms']:.3f} | {r['after_wall_ms']:.3f} |"
        )
    out = Path(__file__).resolve().parents[1] / "docs" / "benchmarks.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
