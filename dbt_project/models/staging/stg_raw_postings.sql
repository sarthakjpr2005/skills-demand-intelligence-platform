{{
  config(
    materialized = 'view',
    schema = 'staging'
  )
}}

/*
  stg_raw_postings
  ─────────────────────────────────────────────────────────────────────────────
  Layer   : Staging
  Source  : staging.raw_postings  (written by the L4 batch loader)
  Purpose : Light normalisation — cast data types, rename columns to
            project-standard names, and unnest the extracted_skills array
            so each skill gets its own row. No business logic here.
  ─────────────────────────────────────────────────────────────────────────────
*/

with source as (

    select * from {{ source('staging', 'raw_postings') }}

),

renamed as (

    select
        -- Surrogate & trace keys
        id                                          as posting_sk,
        source_id,
        pull_batch_id::text                         as batch_id,

        -- Descriptors
        title,
        company                                     as company_name,
        location_raw,
        city,
        state,
        country,

        -- Dates
        posted_date::timestamptz                    as posted_at,
        date_id::date                               as post_date,

        -- Compensation
        salary_min::numeric                         as salary_min,
        salary_max::numeric                         as salary_max,

        -- Content
        description,
        extracted_skills,                           -- still TEXT[] at this point

        -- Audit
        loaded_at::timestamptz                      as loaded_at

    from source
    where source_id is not null
      and title     is not null

)

select * from renamed
