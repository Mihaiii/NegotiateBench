class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        
        # Track round number (each round has 2 turns - partner then us)
        self.round_num = 1
        self.received_first_offer = False
        
    def _value(self, alloc: list[int]) -> int:
        """Compute my value for an allocation."""
        return sum(a * v for a, v in zip(alloc, self.values))
    
    def _make_offer(self, target_pct: float) -> list[int]:
        """Create an offer targeting a specific percentage of total value."""
        offer = self.counts.copy()
        target = self.total * target_pct
        
        # Remove lowest-value items first to maximize what we keep
        while self._value(offer) > target and sum(offer) > 0:
            # Find item with lowest value per unit that we have > 0
            best_idx = -1
            best_value = float('inf')
            for i in range(len(offer)):
                if offer[i] > 0 and self.values[i] < best_value:
                    best_value = self.values[i]
                    best_idx = i
            
            if best_idx >= 0:
                offer[best_idx] -= 1
            else:
                break
        
        # Ensure we don't ask for nothing if we can get something
        if self._value(offer) == 0 and sum(self.counts) > 0:
            best_idx = max(range(len(self.values)), key=lambda i: self.values[i])
            if self.values[best_idx] > 0:
                offer[best_idx] = min(1, self.counts[best_idx])
        
        return offer
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        # First turn: o is None
        if o is None:
            # Opening offer: aim for ~45% and gradually reduce
            # More aggressive opening to get better deals
            progress = min(1.0, (self.round_num - 1) / max(1, self.max_rounds - 1))
            target = 0.45 - progress * 0.20
            return self._make_offer(target)
        
        # Received an offer - check if we should accept
        offer_value = self._value(o)
        
        # Calculate acceptable threshold - starts high and decreases
        progress = min(1.0, (self.round_num - 1) / max(1, self.max_rounds - 1))
        min_accept_pct = 0.40 - progress * 0.25
        min_accept = self.total * min_accept_pct
        
        # Accept if offer is good enough
        if offer_value >= min_accept:
            return None  # Accept the offer
        
        # Make counter-offer and advance round
        self.round_num += 1
        
        # Our target for counter-offers - slightly more than what we'd accept
        target_pct = min_accept_pct + 0.08
        return self._make_offer(target_pct)