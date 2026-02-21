class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.turn = 0
        self.total_turns = max_rounds * 2
        self.last_offer = None
        
    def _value(self, alloc: list[int]) -> int:
        return sum(a * v for a, v in zip(alloc, self.values))
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        progress = min(1.0, (self.turn - 1) / self.total_turns)
        
        if o is None:
            # First offer: start at 65% - be more aggressive
            target = int(self.total * 0.65)
            self.last_offer = self._make_offer(target)
            return self.last_offer
        
        my_value = self._value(o)
        
        # Acceptance threshold: start at 48%, converge to 38% near end
        # Higher than before to avoid accepting bad deals
        min_accept = self.total * (0.48 - 0.10 * progress)
        if my_value >= min_accept:
            return None
        
        # Counteroffer: start at 60%, converge to 48%
        target_pct = 0.60 - 0.12 * progress
        target = int(self.total * target_pct)
        self.last_offer = self._make_offer(target)
        return self.last_offer
    
    def _make_offer(self, target: int) -> list[int]:
        # Sort by value descending
        indices = sorted(range(len(self.values)), 
                        key=lambda i: self.values[i], reverse=True)
        
        offer = [0] * len(self.counts)
        remaining = self.counts.copy()
        
        # Take items greedily until target
        for idx in indices:
            while remaining[idx] > 0 and self._value(offer) + self.values[idx] <= target:
                offer[idx] += 1
                remaining[idx] -= 1
        
        # Take remaining items
        for idx in indices:
            while remaining[idx] > 0:
                offer[idx] += 1
                remaining[idx] -= 1
        
        return offer