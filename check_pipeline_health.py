"""
Level 7: Quick CLI Health Check Script
Run anytime from the project root:
  python check_pipeline_health.py
  python check_pipeline_health.py --health-summary
"""

from src.monitoring.runner import main

if __name__ == "__main__":
    main()
