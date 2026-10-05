{{
  config(
    materialized = 'table',
    schema = 'marts',
    unique_key = ['posting_sk', 'skill_sk']
  )
}}

/*
  fct_posting_skills  (Bridge / Many-to-Many Fact)
  ─────────────────────────────────────────────────────────────────────────────
  Layer   : Marts / Bridge Fact
  Purpose : Resolves the many-to-many relationship between job postings and
            skills. One row per (posting, skill) pair.
            This is the primary analytical table for skill demand queries.

  Key queries powered by this table:
    - "Which skills appear most often?" → GROUP BY skill_sk
    - "Which skills co-occur with Python?" → self-join on posting_sk
    - "How has demand for Airflow trended?" → join dim_date via fct_postings
  ─────────────────────────────────────────────────────────────────────────────
*/

with unnested as (

    select * from {{ ref('int_posting_skills_unnested') }}

),

postings as (

    select
        posting_sk,
        source_id,
        company_sk,
        location_sk,
        date_id

    from {{ ref('fct_postings') }}

),

skills as (

    select skill_sk, skill_name

    from {{ ref('dim_skill') }}

)

select
    p.posting_sk,
    s.skill_sk,
    p.company_sk,
    p.location_sk,
    p.date_id,
    u.skill_name,
    u.skill_position

from unnested u

inner join postings p
    on p.source_id = u.source_id

inner join skills s
    on s.skill_name = u.skill_name
