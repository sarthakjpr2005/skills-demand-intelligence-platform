{{
  config(
    materialized = 'table',
    schema = 'marts',
    unique_key = 'company_sk'
  )
}}

/*
  dim_company
  ─────────────────────────────────────────────────────────────────────────────
  Layer   : Marts / Dimension
  Purpose : One row per distinct company name. A surrogate key is generated
            via MD5 hash of the normalised name so it is deterministic
            across runs — no autoincrement dependency.
  ─────────────────────────────────────────────────────────────────────────────
*/

with companies as (

    select distinct
        lower(trim(company_name))               as company_normalised

    from {{ ref('stg_raw_postings') }}
    where company_name is not null
      and trim(company_name) <> ''

)

select
    md5(company_normalised)                     as company_sk,
    company_normalised                          as company_name,
    initcap(company_normalised)                 as company_display_name

from companies
