from app.services.exceptions_player import AppException


class BehaviorNotFound(AppException):
    def __init__(self, behavior_id: str):
        self.behavior_id = behavior_id

        super().__init__(
            message=f"Behavior '{behavior_id}' was not found for this club.",
            code="BEHAVIOR_NOT_FOUND",
            status_code=404,
        )


class BehaviorNotDt(AppException):
    def __init__(self, behavior_id: str):
        self.behavior_id = behavior_id

        super().__init__(
            message=f"Behavior '{behavior_id}' is not a DT behavior.",
            code="BEHAVIOR_NOT_DT",
            status_code=400,
        )

class ManualActionBlockedByDt(AppException):
    def __init__(self):
        super().__init__(
            message="This club is controlled by its DT during this match.",
            code="MANUAL_ACTION_BLOCKED_BY_DT",
            status_code=403,
        )

class NoDtAssigned(AppException):
    def __init__(self):
        super().__init__(
            message="This club has no DT assigned.",
            code="NO_DT_ASSIGNED",
            status_code=404,
        )
