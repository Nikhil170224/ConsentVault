-- DSR SLA: average resolution time, overdue count, per type.
WITH base AS (
    SELECT
        type,
        status,
        created_at,
        completed_at,
        due_date,
        CASE WHEN completed_at IS NOT NULL
             THEN EXTRACT(EPOCH FROM (completed_at - created_at)) / 86400.0
        END AS resolution_days
    FROM dsr_requests
    WHERE organization_id = :org_id
)
SELECT
    type,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE status = 'COMPLETED') AS completed,
    COUNT(*) FILTER (
        WHERE status IN ('RECEIVED', 'VERIFYING', 'IN_PROGRESS') AND due_date < NOW()
    ) AS overdue,
    ROUND(AVG(resolution_days)::numeric, 2) AS avg_resolution_days,
    ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY resolution_days)::numeric, 2) AS median_resolution_days
FROM base
GROUP BY type
ORDER BY type
