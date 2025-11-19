"""Activity tracking component"""


class ActivityTracker:
    def __init__(self):
        self.activity_counts = {
            'mining': 0, 'forestry': 0, 'smithing': 0, 'refining': 0, 'alchemy': 0,
            'engineering': 0, 'enchanting': 0, 'combat': 0
        }

    def record_activity(self, activity_type: str, amount: int = 1):
        if activity_type in self.activity_counts:
            self.activity_counts[activity_type] += amount

    def get_count(self, activity_type: str) -> int:
        return self.activity_counts.get(activity_type, 0)
