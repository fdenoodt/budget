class SavingsTuple:
    def __init__(self, actual_full: float,
                 target_full: float, target_only_pig: float, target_only_investments: float,
                 actual_only_pig: float,
                 actual_only_investments: float, nb_months_ago: int):
        # These are the savings (investments + money pig are both included)
        self.actual = actual_full # both investments and money pig
        self.actual_only_pig = actual_only_pig
        self.actual_only_investments = actual_only_investments

        self.target = target_full
        self.target_only_pig = target_only_pig
        self.target_only_investments = target_only_investments

        self.nb_months_ago = nb_months_ago

    def serialize(self) -> dict:
        return {
            "target": self.target,
            "target_only_pig": self.target_only_pig,
            "target_only_investments": self.target_only_investments,

            "actual": self.actual,  # actual, includes money pig and investments
            "actual_only_pig": self.actual_only_pig,
            "actual_only_investments": self.actual_only_investments,

            "nb_months_ago": self.nb_months_ago
        }
