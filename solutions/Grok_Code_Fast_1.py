class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_turns = 2 * max_rounds
        self.step = 0
        self.counts = counts
        self.values = values
        self.sort_indices = sorted(range(len(counts)), key=lambda i: values[i])  # Ascending order for conceding low-value first

    def offer(self, o: list[int] | None) -> list[int] | None:
        thresh_fraction = min(1.0, self.step / self.max_turns) if self.max_turns > 0 else 0
        thresh = self.total * (0.9 - thresh_fraction * 0.4)  # Start at 90%, end at 50%
        if o is not None:
            offered_value = sum(o[i] * self.values[i] for i in range(len(o)))
            if offered_value >= thresh:
                return None
        self.step += 1
        return self._get_offer(self.step)

    def _get_offer(self, step: int) -> list[int]:
        my_offer = self.counts.copy()
        remaining_concessions = step
        for i in self.sort_indices:
            if remaining_concessions > 0 and my_offer[i] > 0:
                concession = min(remaining_concessions, my_offer[i])
                my_offer[i] -= concession
                remaining_concessions -= concession
                if remaining_concessions == 0:
                    break
        # Ensure the offer is valid (all >=0, <= counts)
        my_offer = [max(0, min(c, self.counts[i])) for i, c in enumerate(my_offer)]
        return my_offer