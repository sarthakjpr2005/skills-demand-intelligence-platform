"""
Analytical Showcase CLI
───────────────────────
Executes analytical SQL queries against the dbt Star Schema (marts)
and displays formatted intelligence reports on skills demand,
salary benchmarks, tech stack co-occurrences, and hiring companies.
"""

import sys
import argparse
from typing import List, Tuple, Any
from tabulate import tabulate

from src.utils.db_connector import get_psycopg2_connection


def execute_and_display(query: str, title: str, headers: List[str]) -> None:
    """Executes an analytical SQL query and prints a formatted ASCII table."""
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    print("\n" + "=" * 78)
    print(f"  {title.upper()}")
    print("=" * 78)

    if not rows:
        print("  (No records matched query criteria)\n")
        return

    # Render table with clean ASCII psql formatting
    table_str = tabulate(rows, headers=headers, tablefmt="psql", numalign="right")
    print(table_str)
    print(f"  Total records: {len(rows)}\n")



def show_top_skills():
    query = """
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
    """
    execute_and_display(
        query=query,
        title="1. Top 15 Most Demanded Tech Skills",
        headers=["Skill", "Category", "Postings Count", "Market Share %"]
    )


def show_category_breakdown():
    query = """
        SELECT
            s.skill_category,
            COUNT(DISTINCT s.skill_sk) AS unique_skills_tracked,
            COUNT(f.posting_sk) AS total_skill_mentions,
            COALESCE(ROUND(AVG(p.salary_midpoint), 0)::text, 'N/A') AS avg_category_salary
        FROM marts.fct_posting_skills f
        JOIN marts.dim_skill s ON f.skill_sk = s.skill_sk
        LEFT JOIN marts.fct_postings p ON f.posting_sk = p.posting_sk AND p.salary_midpoint IS NOT NULL
        GROUP BY s.skill_category
        ORDER BY total_skill_mentions DESC;
    """
    execute_and_display(
        query=query,
        title="2. Skill Demand by Taxonomy Category",
        headers=["Category", "Unique Skills", "Total Mentions", "Avg Salary (GBP)"]
    )


def show_skill_cooccurrences():
    query = """
        SELECT
            s1.skill_display_name AS primary_skill,
            s2.skill_display_name AS co_occurring_skill,
            COUNT(*) AS co_occurrence_count
        FROM marts.fct_posting_skills f1
        JOIN marts.fct_posting_skills f2
            ON f1.posting_sk = f2.posting_sk
            AND f1.skill_sk < f2.skill_sk
        JOIN marts.dim_skill s1 ON f1.skill_sk = s1.skill_sk
        JOIN marts.dim_skill s2 ON f2.skill_sk = s2.skill_sk
        GROUP BY s1.skill_display_name, s2.skill_display_name
        HAVING COUNT(*) >= 1
        ORDER BY co_occurrence_count DESC
        LIMIT 10;
    """
    execute_and_display(
        query=query,
        title="3. Tech Stack Co-occurrence Pairs (Skills Frequently Demanded Together)",
        headers=["Primary Skill", "Co-Occurring Skill", "Joint Postings Count"]
    )


def show_salary_benchmarks():
    query = """
        SELECT
            s.skill_display_name,
            s.skill_category,
            COUNT(p.posting_sk) AS postings_with_salary,
            ROUND(MIN(p.salary_min), 0) AS min_salary,
            ROUND(AVG(p.salary_midpoint), 0) AS avg_midpoint,
            ROUND(MAX(p.salary_max), 0) AS max_salary
        FROM marts.fct_posting_skills f
        JOIN marts.dim_skill s ON f.skill_sk = s.skill_sk
        JOIN marts.fct_postings p ON f.posting_sk = p.posting_sk
        WHERE p.salary_midpoint IS NOT NULL
        GROUP BY s.skill_display_name, s.skill_category
        ORDER BY avg_midpoint DESC
        LIMIT 10;
    """


    execute_and_display(
        query=query,
        title="4. Salary Benchmarks by Tech Skill (Disclosed Compensation)",
        headers=["Skill", "Category", "Postings", "Min Salary", "Avg Midpoint", "Max Salary"]
    )


def show_top_hiring_companies():
    query = """
        SELECT
            c.company_name,
            COUNT(DISTINCT f.posting_sk) AS active_postings,
            COALESCE(ROUND(AVG(f.salary_midpoint), 0)::text, 'Not Disclosed') AS avg_salary,
            ARRAY_TO_STRING(
                ARRAY(
                    SELECT s.skill_display_name
                    FROM marts.fct_posting_skills fps
                    JOIN marts.dim_skill s ON fps.skill_sk = s.skill_sk
                    WHERE fps.company_sk = c.company_sk
                    GROUP BY s.skill_display_name
                    ORDER BY COUNT(*) DESC
                    LIMIT 4
                ), ', '
            ) AS top_demanded_skills
        FROM marts.fct_postings f
        JOIN marts.dim_company c ON f.company_sk = c.company_sk
        WHERE c.company_name != 'Unknown'
        GROUP BY c.company_sk, c.company_name
        ORDER BY active_postings DESC
        LIMIT 10;
    """
    execute_and_display(
        query=query,
        title="5. Top Hiring Companies and Core Tech Stacks",
        headers=["Company", "Active Postings", "Avg Salary", "Demanded Skills"]
    )


def show_geographic_distribution():
    query = """
        SELECT
            COALESCE(l.city, 'Not Specified') AS city,
            COALESCE(l.country, 'Not Specified') AS country,
            COUNT(f.posting_sk) AS total_postings,
            COALESCE(ROUND(AVG(f.salary_midpoint), 0)::text, 'N/A') AS avg_salary
        FROM marts.fct_postings f
        JOIN marts.dim_location l ON f.location_sk = l.location_sk
        GROUP BY l.city, l.country
        ORDER BY total_postings DESC
        LIMIT 10;
    """
    execute_and_display(
        query=query,
        title="6. Geographic Hubs of Engineering Demand",
        headers=["City", "Country", "Postings", "Avg Salary"]
    )


def main():
    parser = argparse.ArgumentParser(
        description="Skills Demand Intelligence Platform — Analytics Showcase"
    )
    parser.add_argument(
        "--report",
        type=str,
        default="all",
        choices=["all", "skills", "categories", "cooccur", "salary", "companies", "geo"],
        help="Specify which report section to run (default: all)"
    )
    args = parser.parse_args()

    reports = {
        "skills": show_top_skills,
        "categories": show_category_breakdown,
        "cooccur": show_skill_cooccurrences,
        "salary": show_salary_benchmarks,
        "companies": show_top_hiring_companies,
        "geo": show_geographic_distribution,
    }

    if args.report == "all":
        for report_fn in reports.values():
            report_fn()
    else:
        reports[args.report]()


if __name__ == "__main__":
    main()
