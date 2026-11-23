-- Withdrawal trends with running totals (window functions).
WITH daily AS (
    SELECT
        DATE(e.created_at) AS day,
        COUNT(*) AS withdrawals
    FROM consent_events e
    WHERE e.organization_id = :org_id
      AND e.event_type = 'consent.withdrawn'
    GROUP BY DATE(e.created_at)
)
SELECT
    day,
    withdrawals,
    SUM(withdrawals) OVER (ORDER BY day) AS running_total,
    AVG(withdrawals) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS moving_avg_7d,
    RANK() OVER (ORDER BY withdrawals DESC) AS rank_by_volume
FROM daily
ORDER BY day DESC
LIMIT 500
