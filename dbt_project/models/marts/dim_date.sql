{{
  config(
    materialized = 'table',
    schema = 'marts',
    unique_key = 'date_id'
  )
}}

/*
  dim_date
  ─────────────────────────────────────────────────────────────────────────────
  Layer   : Marts / Dimension
  Purpose : Calendar dimension with pre-computed attributes for any date
            that appears in fct_postings. Avoids repeated date arithmetic
            inside every analytical query.
  ─────────────────────────────────────────────────────────────────────────────
*/

with date_spine as (

    select distinct
        post_date as date_id

    from {{ ref('stg_raw_postings') }}
    where post_date is not null

)

select
    date_id,
    extract(year  from date_id)::int            as year,
    extract(month from date_id)::int            as month_num,
    to_char(date_id, 'Month')                   as month_name,
    extract(quarter from date_id)::int          as quarter,
    extract(week from date_id)::int             as iso_week,
    extract(dow from date_id)::int              as day_of_week,   -- 0 = Sunday
    to_char(date_id, 'Day')                     as day_name,
    to_char(date_id, 'YYYY-"Q"Q')              as year_quarter,
    to_char(date_id, 'YYYY-MM')                as year_month,
    (extract(dow from date_id) in (0, 6))       as is_weekend

from date_spine
order by date_id
