class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.me = me
        self.max_rounds = max_rounds
        self.round = 0
        self.total = sum(c * v for c, v in zip(counts, values))
        # Compute best possible allocation for myself (max value to me)
        self.best_allocation = self._compute_best_allocation()

    def _compute_best_allocation(self) -> list[int]:
        """Compute allocation that maximizes my value."""
        # Start with all items
        alloc = self.counts.copy()
        # Remove items worth 0 to me
        for i in range(len(self.values)):
            if self.values[i] == 0:
                alloc[i] = 0
        return alloc

    def _compute_value(self, allocation: list[int]) -> int:
        """Compute my value for an allocation."""
        return sum(a * v for a, v in zip(allocation, self.values))

    def _get_threshold(self) -> float:
        """Get minimum value threshold based on remaining rounds."""
        # Decline threshold as rounds decrease
        # Start high, but accept less as time runs out
        remaining = self.max_rounds - self.round
        if remaining <= 0:
            return 0.0
        # Linear decline from ~60% to ~30% of total value
        return max(0.3, 0.6 - (self.max_rounds - remaining) * 0.3 / max(1, self.max_rounds))

    def offer(self, o: list[int] | None) -> list[int] | None:
        # First turn: me == 0 and o is None
        if o is None:
            # My first offer - propose a fair split
            my_offer = self.best_allocation.copy()
            # Scale down if too greedy (give partner at least 40%)
            my_value = self._compute_value(my_offer)
            if my_value > self.total * 0.6:
                # Reduce some items to be more reasonable
                for i in range(len(self.counts)):
                    if self.counts[i] > 0 and self.values[i] > 0:
                        my_offer[i] = max(0, my_offer[i] - 1)
                        if self._compute_value(my_offer) <= self.total * 0.6:
                            break
            return my_offer

        # Increment round counter when I receive an offer
        self.round += 1

        # Calculate value of offer to me
        offer_value = self._compute_value(o)
        threshold = self._get_threshold() * self.total

        # Accept if offer meets threshold
        if offer_value >= threshold:
            return None

        # Counter-offer: try to get best value while being reasonable
        # Give partner at least what they offered (inferred from their preference)
        # Start with my best, then compromise based on rounds left
        
        remaining = self.max_rounds - self.round
        if remaining <= 1:
            # Last chance - accept almost anything
            if offer_value > 0:
                return o  # Accept their offer by mirroring it (they get what they offered)
            # If offer is 0, try my best anyway
            return self.best_allocation

        # Make a counter-offer: start with my best, gradually reduce
        counter = self.best_allocation.copy()
        
        # Try to find a reasonable middle ground
        # Give partner some items they seem to want (based on their offer)
        partner_items = [self.counts[i] - o[i] for i in range(len(o))]
        
        # Reduce my demands slightly each round
        for i in range(len(self.values)):
            if counter[i] > 0 and self.values[i] > 0:
                # Keep at least some items valuable to me
                if self._compute_value(counter) > threshold * 1.2:
                    counter[i] = max(0, counter[i] - 1)
        
        return counter