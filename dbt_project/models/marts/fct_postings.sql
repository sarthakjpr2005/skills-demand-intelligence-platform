{{
  config(
    materialized = 'table',
    schema = 'marts',
    unique_key = 'posting_sk'
  )
}}

/*
  fct_postings
  ─────────────────────────────────────────────────────────────────────────────
  Layer   : Marts / Fact
  Purpose : One row per unique job posting. Joins to dimension tables via
            surrogate keys. Deduplication across batches is enforced here
            by selecting DISTINCT ON source_id and taking the latest load.
            Measures: salary_min, salary_max, skill_count.
  ─────────────────────────────────────────────────────────────────────────────
*/

with staged as (

    select * from {{ ref('stg_raw_postings') }}

),

-- Deduplicate: for a given source_id, keep only the latest-loaded version
deduped as (

    select distinct on (source_id)
        posting_sk,
        source_id,
        batch_id,
        title,
        company_name,
        post_date,
        posted_at,
        salary_min,
        salary_max,
        description,
        extracted_skills,
        city,
        state,
        country,
        location_raw,
        loaded_at

    from staged
    order by source_id, loaded_at desc

),

-- Join dimension surrogate keys
enriched as (

    select
        d.posting_sk,
        d.source_id,
        d.batch_id,
        d.title,

        -- FK to dim_company
        dc.company_sk,

        -- FK to dim_location
        dl.location_sk,

        -- FK to dim_date
        dd.date_id,

        d.posted_at,
        d.salary_min,
        d.salary_max,
        case
            when d.salary_min is not null and d.salary_max is not null
                then (d.salary_min + d.salary_max) / 2.0
        end                                         as salary_midpoint,

        coalesce(cardinality(d.extracted_skills), 0) as skill_count,
        d.description,
        d.loaded_at

    from deduped d

    left join {{ ref('dim_company') }} dc
        on dc.company_name = lower(trim(d.company_name))

    left join {{ ref('dim_location') }} dl
        on  dl.city    = coalesce(lower(trim(d.city)),    'unknown')
        and dl.state   = coalesce(lower(trim(d.state)),   'unknown')
        and dl.country = coalesce(lower(trim(d.country)), 'unknown')

    left join {{ ref('dim_date') }} dd
        on dd.date_id = d.post_date

)

select * from enriched
