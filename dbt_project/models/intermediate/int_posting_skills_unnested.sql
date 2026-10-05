{{
  config(
    materialized = 'view',
    schema = 'intermediate'
  )
}}

/*
  int_posting_skills_unnested
  ─────────────────────────────────────────────────────────────────────────────
  Layer   : Intermediate
  Source  : stg_raw_postings
  Purpose : Explode the TEXT[] extracted_skills array into one row per
            (posting, skill) pair. This is the bridge-table foundation.

            UNNEST with ORDINALITY preserves order and produces a clean
            skill_position column useful for future frequency analysis.
  ─────────────────────────────────────────────────────────────────────────────
*/

with staged as (

    select
        posting_sk,
        source_id,
        extracted_skills

    from {{ ref('stg_raw_postings') }}
    where extracted_skills is not null
      and cardinality(extracted_skills) > 0

),

unnested as (

    select
        s.posting_sk,
        s.source_id,
        lower(trim(skill_name))     as skill_name,
        skill_pos                   as skill_position

    from staged s,
         unnest(s.extracted_skills) with ordinality as t(skill_name, skill_pos)

)

select * from unnested
where skill_name <> ''
