class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        # Compute my best possible allocation (maximize my value)
        self.best_allocation = self._compute_best()
        # Track round number (increments each time we make an offer)
        self.round = 0
        
    def _compute_best(self) -> list[int]:
        """Compute allocation that maximizes my value."""
        alloc = self.counts.copy()
        for i in range(len(self.values)):
            if self.values[i] == 0:
                alloc[i] = 0
        return alloc
    
    def _value(self, alloc: list[int]) -> int:
        """Compute my value for an allocation."""
        return sum(a * v for a, v in zip(alloc, self.values))
    
    def _threshold(self) -> float:
        """Minimum value I'll accept, declining as rounds run out."""
        # Start with 45% and decline to 25% as time runs out
        progress = self.round / max(1, self.max_rounds)
        return max(0.25, 0.45 - progress * 0.2)
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        # First turn: o is None
        if o is None:
            # If I'm second (me=1), return None to wait for first offer
            if self.me == 1:
                return None
            
            # First offer: propose a fair split (~55% for me)
            offer = self.best_allocation.copy()
            target = self.total * 0.55
            
            # Reduce items until we hit target
            while self._value(offer) > target:
                # Remove from lowest value-to-count ratio items first
                for i in range(len(self.values)):
                    if offer[i] > 0 and self.values[i] > 0:
                        offer[i] -= 1
                        break
            return offer
        
        # Received an offer - check if I should accept
        offer_value = self._value(o)
        min_accept = self.total * self._threshold()
        
        # Check if this is my turn or partner's (o is partner's offer)
        # Increment round when I make a counter-offer
        self.round += 1
        
        if offer_value >= min_accept:
            # Accept!
            return None
        
        # Make counter-offer
        # Strategy: start from best, gradually concede based on remaining rounds
        remaining = self.max_rounds - self.round
        target = self.total * max(0.30, 0.55 - (self.round / max(1, self.max_rounds)) * 0.25)
        
        counter = self.best_allocation.copy()
        
        # Concede more as time runs out
        # Reduce items from low-value-per-unit items first
        items_to_remove = min(remaining + 1, sum(self.counts))
        
        while self._value(counter) > target and items_to_remove > 0:
            # Find item with lowest value-to-count ratio
            best_idx = -1
            best_ratio = float('inf')
            for i in range(len(counter)):
                if counter[i] > 0 and self.values[i] > 0:
                    ratio = self.values[i]  # Higher value = keep longer
                    if ratio < best_ratio:
                        best_ratio = ratio
                        best_idx = i
            
            if best_idx >= 0:
                counter[best_idx] -= 1
                items_to_remove -= 1
            else:
                break
        
        return counter