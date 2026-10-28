"""Minimal evaluator for the custom_alarms.json rule format."""

import json


class CustomAlarmEngine:
    def __init__(self, alarm_sampling, config_path):
        self.alarm_sampling = alarm_sampling
        self.rules = json.loads(config_path.read_text(encoding="utf-8"))
        self.active_rules = set()

    async def process(self, device_id, device_type, latest_values, timestamp):
        if not device_id or not device_type:
            return

        for name, rule in self.rules.items():
            profile = rule.get("device_profile", {})
            if profile.get("device_type") not in (None, device_type):
                continue

            key = (device_id, name)
            if self._matches(rule.get("raise_condition", []), latest_values):
                if key not in self.active_rules:
                    await self.alarm_sampling.add_data(
                        device_id, name, 1, timestamp, alarmType="custom",
                        customInfos=rule,
                    )
                    self.active_rules.add(key)
            elif key in self.active_rules and self._matches(
                rule.get("clear_condition", []), latest_values
            ):
                await self.alarm_sampling.add_data(
                    device_id, name, 0, timestamp, alarmType="custom",
                    customInfos=rule,
                )
                self.active_rules.remove(key)

    def _matches(self, groups, values):
        return any(
            all(
                self._matches_filter(item, values)
                for item in group.get("key_filter", [])
            )
            for group in groups
        )

    @staticmethod
    def _matches_filter(item, values):
        value = values.get(item.get("name"))
        if value is None:
            return False

        for condition in item.get("conditions", []):
            target = condition.get("value")
            condition_type = condition.get("type")
            if condition_type == "greater_than" and not value > target:
                return False
            if condition_type == "greater_than_equal" and not value >= target:
                return False
            if condition_type == "less_than" and not value < target:
                return False
            if condition_type == "less_than_equal" and not value <= target:
                return False
            if condition_type == "equal" and not value == target:
                return False
        return True
