{{
  config(
    materialized = 'table',
    schema = 'marts',
    unique_key = 'skill_sk'
  )
}}

/*
  dim_skill
  ─────────────────────────────────────────────────────────────────────────────
  Layer   : Marts / Dimension
  Purpose : One row per distinct skill name extracted across all postings.
            Skill category is enriched from the skills taxonomy config.
            Surrogate key is an MD5 of the normalised skill name.
  ─────────────────────────────────────────────────────────────────────────────
*/

with skills as (

    select distinct
        lower(trim(skill_name)) as skill_name

    from {{ ref('int_posting_skills_unnested') }}
    where skill_name is not null
      and trim(skill_name) <> ''

)

select
    md5(skill_name)     as skill_sk,
    skill_name,
    initcap(skill_name) as skill_display_name,
    /*
      Category is a manual enrichment based on the taxonomy defined in
      config/skills_taxonomy.py. In a production system this would be
      driven by a seed CSV loaded into the warehouse.
    */
    case skill_name
        when 'python'       then 'language'
        when 'sql'          then 'language'
        when 'scala'        then 'language'
        when 'java'         then 'language'
        when 'r'            then 'language'
        when 'bash'         then 'language'
        when 'postgresql'   then 'database'
        when 'mysql'        then 'database'
        when 'mongodb'      then 'database'
        when 'clickhouse'   then 'database'
        when 'snowflake'    then 'warehouse'
        when 'bigquery'     then 'warehouse'
        when 'redshift'     then 'warehouse'
        when 'airflow'      then 'orchestration'
        when 'prefect'      then 'orchestration'
        when 'dagster'      then 'orchestration'
        when 'dbt'          then 'transformation'
        when 'spark'        then 'processing'
        when 'kafka'        then 'streaming'
        when 'flink'        then 'streaming'
        when 'aws'          then 'cloud'
        when 'gcp'          then 'cloud'
        when 'azure'        then 'cloud'
        when 'databricks'   then 'platform'
        when 'docker'       then 'platform'
        when 'kubernetes'   then 'platform'
        when 'terraform'    then 'iac'
        when 'git'          then 'tool'
        when 'tableau'      then 'bi'
        when 'power bi'     then 'bi'
        else                     'other'
    end                 as skill_category

from skills
