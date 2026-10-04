"""
Curated Skills Taxonomy
Dictionary defining target skills, categories, and regex boundary patterns.
"""

SKILLS_TAXONOMY = {
    # Programming Languages
    "python": {"category": "language", "pattern": r"\bpython\b"},
    "sql": {"category": "language", "pattern": r"\bsql\b"},
    "scala": {"category": "language", "pattern": r"\bscala\b"},
    "java": {"category": "language", "pattern": r"\bjava\b(?!\s*script)"},
    "r": {"category": "language", "pattern": r"\br\b(?=\s*(?:programming|script|package|studio))"},
    "bash": {"category": "language", "pattern": r"\b(?:bash|shell)\b"},

    # Databases & Warehouses
    "postgresql": {"category": "database", "pattern": r"\bpostgres(?:ql)?\b"},
    "mysql": {"category": "database", "pattern": r"\bmysql\b"},
    "snowflake": {"category": "warehouse", "pattern": r"\bsnowflake\b"},
    "bigquery": {"category": "warehouse", "pattern": r"\bbigquery\b"},
    "redshift": {"category": "warehouse", "pattern": r"\bredshift\b"},
    "mongodb": {"category": "database", "pattern": r"\bmongodb\b"},
    "clickhouse": {"category": "database", "pattern": r"\bclickhouse\b"},

    # Orchestration & Data Engineering Frameworks
    "airflow": {"category": "orchestration", "pattern": r"\b(?:apache\s*)?airflow\b"},
    "dbt": {"category": "transformation", "pattern": r"\bdbt\b"},
    "spark": {"category": "processing", "pattern": r"\b(?:apache\s*)?spark\b"},
    "kafka": {"category": "streaming", "pattern": r"\b(?:apache\s*)?kafka\b"},
    "flink": {"category": "streaming", "pattern": r"\b(?:apache\s*)?flink\b"},
    "prefect": {"category": "orchestration", "pattern": r"\bprefect\b"},
    "dagster": {"category": "orchestration", "pattern": r"\bdagster\b"},

    # Cloud & Infrastructure
    "aws": {"category": "cloud", "pattern": r"\b(?:aws|amazon web services)\b"},
    "gcp": {"category": "cloud", "pattern": r"\b(?:gcp|google cloud(?: platform)?)\b"},
    "azure": {"category": "cloud", "pattern": r"\b(?:azure|microsoft azure)\b"},
    "databricks": {"category": "platform", "pattern": r"\bdatabricks\b"},
    "docker": {"category": "platform", "pattern": r"\bdocker\b"},
    "kubernetes": {"category": "platform", "pattern": r"\b(?:kubernetes|k8s)\b"},
    "terraform": {"category": "iac", "pattern": r"\bterraform\b"},
    "git": {"category": "tool", "pattern": r"\bgit\b"},

    # BI & Analytics
    "tableau": {"category": "bi", "pattern": r"\btableau\b"},
    "power bi": {"category": "bi", "pattern": r"\bpower\s*bi\b"}
}
