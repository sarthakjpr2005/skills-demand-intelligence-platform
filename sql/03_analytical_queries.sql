-- =============================================================================
-- Analytical SQL Showcase
-- Skills Demand Intelligence Platform
-- Target Schema: marts (dim_skill, dim_company, dim_location, dim_date, fct_postings, fct_posting_skills)
-- =============================================================================

-- =============================================================================
-- Query 1: Top 15 Most Demanded Skills Across All Job Postings
-- Demonstrates bridge table aggregation with dim_skill metadata
-- =============================================================================
SELECT
    s.skill_display_name,
    s.skill_category,
    COUNT(DISTINCT f.posting_sk) AS total_postings,
    ROUND(100.0 * COUNT(DISTINCT f.posting_sk) / (SELECT COUNT(*) FROM marts.fct_postings), 2) AS market_penetration_pct
FROM marts.fct_posting_skills f
JOIN marts.dim_skill s ON f.skill_sk = s.skill_sk
GROUP BY s.skill_display_name, s.skill_category
ORDER BY total_postings DESC
LIMIT 15;


-- =============================================================================
-- Query 2: Skill Demand Grouped by Taxonomy Category
-- Evaluates which technology categories have the highest aggregate mentions
-- =============================================================================
SELECT
    s.skill_category,
    COUNT(DISTINCT s.skill_sk) AS unique_skills_tracked,
    COUNT(f.posting_sk) AS total_skill_mentions,
    ROUND(AVG(p.salary_midpoint), 2) AS avg_category_salary
FROM marts.fct_posting_skills f
JOIN marts.dim_skill s ON f.skill_sk = s.skill_sk
LEFT JOIN marts.fct_postings p ON f.posting_sk = p.posting_sk AND p.salary_midpoint IS NOT NULL
GROUP BY s.skill_category
ORDER BY total_skill_mentions DESC;


-- =============================================================================
-- Query 3: Tech Stack Co-occurrence Matrix (Skills that appear together)
-- Self-joins the bridge table to discover which skills are demanded together
-- e.g. How often Python and AWS appear in the same posting
-- =============================================================================
SELECT
    s1.skill_display_name AS primary_skill,
    s2.skill_display_name AS co_occurring_skill,
    COUNT(*) AS co_occurrence_count
FROM marts.fct_posting_skills f1
JOIN marts.fct_posting_skills f2
    ON f1.posting_sk = f2.posting_sk
    AND f1.skill_sk < f2.skill_sk  -- Prevent reverse duplicates (A-B and B-A) and self-joins
JOIN marts.dim_skill s1 ON f1.skill_sk = s1.skill_sk
JOIN marts.dim_skill s2 ON f2.skill_sk = s2.skill_sk
GROUP BY s1.skill_display_name, s2.skill_display_name
HAVING COUNT(*) > 1
ORDER BY co_occurrence_count DESC
LIMIT 15;


-- =============================================================================
-- Query 4: Salary Benchmark by Tech Skill
-- Calculates salary percentiles and averages for roles requiring specific skills
-- Filters for postings with disclosed compensation
-- =============================================================================
SELECT
    s.skill_display_name,
    s.skill_category,
    COUNT(p.posting_sk) AS postings_with_salary,
    ROUND(MIN(p.salary_min), 0) AS min_salary_disclosed,
    ROUND(AVG(p.salary_midpoint), 0) AS avg_midpoint_salary,
    ROUND(MAX(p.salary_max), 0) AS max_salary_disclosed
FROM marts.fct_posting_skills f
JOIN marts.dim_skill s ON f.skill_sk = s.skill_sk
JOIN marts.fct_postings p ON f.posting_sk = p.posting_sk
WHERE p.salary_midpoint IS NOT NULL
GROUP BY s.skill_display_name, s.skill_category
HAVING COUNT(p.posting_sk) >= 1
ORDER BY avg_midpoint_salary DESC
LIMIT 15;




-- =============================================================================
-- Query 5: Top Hiring Companies and Their Primary Tech Stack
-- Aggregates distinct postings per company along with an array of their demanded skills
-- =============================================================================
SELECT
    c.company_name,
    COUNT(DISTINCT f.posting_sk) AS active_postings,
    ROUND(AVG(f.salary_midpoint), 0) AS avg_company_salary,
    ARRAY_TO_STRING(
        ARRAY(
            SELECT s.skill_display_name
            FROM marts.fct_posting_skills fps
            JOIN marts.dim_skill s ON fps.skill_sk = s.skill_sk
            WHERE fps.company_sk = c.company_sk
            GROUP BY s.skill_display_name
            ORDER BY COUNT(*) DESC
            LIMIT 5
        ), ', '
    ) AS top_demanded_skills
FROM marts.fct_postings f
JOIN marts.dim_company c ON f.company_sk = c.company_sk
WHERE c.company_name != 'Unknown'
GROUP BY c.company_sk, c.company_name
ORDER BY active_postings DESC
LIMIT 10;


-- =============================================================================
-- Query 6: Geographic Distribution of Tech Demand
-- Identifies top tech hiring hubs by city, state, and country
-- =============================================================================
SELECT
    COALESCE(l.city, 'Not Specified') AS city,
    COALESCE(l.state, 'Not Specified') AS state,
    COALESCE(l.country, 'Not Specified') AS country,
    COUNT(f.posting_sk) AS total_postings,
    ROUND(AVG(f.salary_midpoint), 0) AS avg_salary
FROM marts.fct_postings f
JOIN marts.dim_location l ON f.location_sk = l.location_sk
GROUP BY l.city, l.state, l.country
ORDER BY total_postings DESC
LIMIT 10;


-- =============================================================================
-- Query 7: Pipeline Observability & Ingestion Audit
-- Summarizes historical pipeline executions from the monitoring view
-- =============================================================================
SELECT
    run_id,
    started_at::date AS run_date,
    duration_seconds,
    records_fetched,
    records_loaded,
    records_duped,
    quarantine_failure_rate_pct,
    checks_passed,
    checks_warned,
    checks_failed,
    status
FROM monitoring.v_pipeline_health
ORDER BY started_at DESC
LIMIT 5;
