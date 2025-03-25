class SavingsTuple:
    def __init__(self, actual: float, target: float) -> None:
        self.value = actual
        self.target = target

    def serialize(self) -> dict:
        return {
            "value": self.value,
            "target": self.target
        }
