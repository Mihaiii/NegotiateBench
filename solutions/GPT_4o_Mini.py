class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(count * value for count, value in zip(counts, values))

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.max_rounds -= 1

        if o is not None:
            partner_value = sum(value * count for value, count in zip(self.values, o))
            # Accept the offer if it provides at least half of the total value
            if partner_value >= self.total_value / 2:
                return None

        # Propose to take all items with positive value that I can
        proposed_offer = self.counts.copy()
        for i in range(len(proposed_offer)):
            if self.values[i] == 0:
                proposed_offer[i] = 0

        return proposed_offer