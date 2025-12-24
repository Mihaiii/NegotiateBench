class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.me = me
        self.max_rounds = max_rounds
        self.turn_count = 0
        
        # Pre-compute item indices sorted by value (descending) to efficiently construct offers
        self.sorted_indices = sorted(range(len(counts)), key=lambda i: values[i], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        
        # 1. Check for Acceptance
        if o is not None:
            offer_val = sum(self.values[i] * o[i] for i in range(len(self.counts)))
            
            # Accept if the offer gives us at least half of the total value
            if offer_val >= self.total_value / 2:
                return None
            
            # If this is the very last turn of the negotiation, accept anything positive
            # (Something is better than nothing)
            if self.turn_count >= total_turns:
                if offer_val > 0:
                    return None

        # 2. Generate Counter-Offer
        # Check if this is the turn BEFORE the last turn.
        # If we are at turn `total_turns - 1`, the opponent will get turn `total_turns`.
        # If the opponent rejects our offer at `total_turns - 1`, the game ends with 0.
        # Therefore, we MUST make an offer that is likely to be accepted at this stage.
        # We assume a "Fair" split (50% of our value) is acceptable to a rational opponent
        # who might otherwise get nothing.
        if self.turn_count == total_turns - 1:
            return self._generate_fair_offer()
        
        # Otherwise, be aggressive: Demand all items with non-zero value
        return self._generate_max_offer()

    def _generate_max_offer(self) -> list[int]:
        """Demand all items that have value to us."""
        offer = [0] * len(self.counts)
        for i in range(len(self.counts)):
            if self.values[i] > 0:
                offer[i] = self.counts[i]
        return offer

    def _generate_fair_offer(self) -> list[int]:
        """Generate an offer worth approximately 50% of our total value."""
        target_value = self.total_value / 2.0
        current_value = 0.0
        offer = [0] * len(self.counts)
        
        # Greedily select the most valuable items to us until we reach the target
        for i in self.sorted_indices:
            if current_value >= target_value:
                break
            
            # Take all available of this item type if it helps us reach the target
            # and we haven't taken it yet.
            count = self.counts[i]
            val = self.values[i]
            
            # Check if taking all of this type exceeds the target significantly
            # Since items are discrete, we just take them if we still need value.
            if val > 0:
                offer[i] = count
                current_value += count * val
        
        return offer