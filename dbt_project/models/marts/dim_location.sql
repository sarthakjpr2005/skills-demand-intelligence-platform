{{
  config(
    materialized = 'table',
    schema = 'marts',
    unique_key = 'location_sk'
  )
}}

/*
  dim_location
  ─────────────────────────────────────────────────────────────────────────────
  Layer   : Marts / Dimension
  Purpose : One row per distinct (city, state, country) combination.
            Surrogate key is an MD5 of the concatenated normalised values.
  ─────────────────────────────────────────────────────────────────────────────
*/

with locations as (

    select distinct
        coalesce(lower(trim(city)),    'unknown')  as city_norm,
        coalesce(lower(trim(state)),   'unknown')  as state_norm,
        coalesce(lower(trim(country)), 'unknown')  as country_norm,
        location_raw

    from {{ ref('stg_raw_postings') }}

)

select
    md5(city_norm || '|' || state_norm || '|' || country_norm) as location_sk,
    city_norm                           as city,
    state_norm                          as state,
    country_norm                        as country,
    initcap(city_norm)                  as city_display,
    initcap(state_norm)                 as state_display,
    upper(country_norm)                 as country_display,
    location_raw

from locations
