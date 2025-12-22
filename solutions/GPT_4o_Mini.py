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
            # Accept the offer if the partner's value is at least half of the total value
            if partner_value >= self.total_value / 2:
                return None

        # Create a proposed offer to maximize our value
        proposed_offer = [0] * len(self.counts)
        remaining_value_needed = self.total_value / 2  # Aim for at least half of total value

        for i in range(len(self.counts)):
            if self.values[i] > 0 and remaining_value_needed > 0:
                # Calculate how many of this item we can take without exceeding the remaining value needed
                max_take = remaining_value_needed // self.values[i]
                proposed_offer[i] = min(max_take, self.counts[i])
                remaining_value_needed -= proposed_offer[i] * self.values[i]

            # If we meet our target value, stop allocating further
            if remaining_value_needed <= 0:
                break

        # To ensure all items are allocated as required
        for i in range(len(self.counts)):
            if proposed_offer[i] > self.counts[i]:
                proposed_offer[i] = self.counts[i]  # Adjust to not exceed available counts
        
        return proposed_offer