-- Grant/withdraw counts per purpose per day (CTE + aggregation).
WITH daily AS (
    SELECT
        p.code AS purpose_code,
        DATE(e.created_at) AS day,
        COUNT(*) FILTER (WHERE e.event_type = 'consent.granted') AS grants,
        COUNT(*) FILTER (WHERE e.event_type = 'consent.withdrawn') AS withdrawals
    FROM consent_events e
    JOIN consents c ON c.id = e.consent_id
    JOIN purposes p ON p.id = c.purpose_id
    WHERE e.organization_id = :org_id
    GROUP BY p.code, DATE(e.created_at)
)
SELECT
    purpose_code,
    day,
    grants,
    withdrawals,
    CASE WHEN grants + withdrawals > 0
         THEN ROUND(100.0 * grants / (grants + withdrawals), 2)
         ELSE 0 END AS grant_rate_pct
FROM daily
ORDER BY day DESC, purpose_code
LIMIT 500
