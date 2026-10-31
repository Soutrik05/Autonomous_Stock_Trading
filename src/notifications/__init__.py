"""
In-App Transparency Activity Feed and Health Alerts.
Provides structured event logging to the activity_log SQLite table for frontend consumption.
"""
from notifications.alerts import count_consecutive_failures, record_pipeline_failure

__all__ = ["count_consecutive_failures", "record_pipeline_failure"]
