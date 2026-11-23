# ConsentVault Benchmarks

Measured with `EXPLAIN (ANALYZE, BUFFERS)` and median wall-clock of 5 runs.
Only measured numbers are reported — rerun `scripts/benchmark_queries.py` to reproduce.

Row counts at benchmark time: {'data_subjects': 1998, 'consents': 3996, 'consent_events': 4581, 'dsr_requests': 200}

| Query | Before EXPLAIN (ms) | Before wall median (ms) | After EXPLAIN (ms) | After wall median (ms) |
|---|---|---|---|---|
| consent_check | 0.069 | 0.593 | 0.050 | 0.647 |
| report_consent_rates | 5.831 | 9.867 | 3.310 | 3.175 |
| report_withdrawal_trends | 0.486 | 1.210 | 0.235 | 0.752 |
| report_dsr_sla | 0.213 | 0.841 | 0.197 | 0.745 |
