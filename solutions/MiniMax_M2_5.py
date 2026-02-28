class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.turn = 0
        self.total_turns = max_rounds * 2
        self.best_received = None
        self.best_received_value = -1
        
    def _value(self, alloc: list[int]) -> int:
        return sum(a * v for a, v in zip(alloc, self.values))
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        progress = min(1.0, (self.turn - 1) / max(1, self.total_turns - 1))
        
        if o is None:
            # First offer: start at 50% of total value - more reasonable
            target = int(self.total * 0.50)
            return self._make_offer(target)
        
        # Track best offer received
        my_value = self._value(o)
        if my_value > self.best_received_value:
            self.best_received_value = my_value
            self.best_received = o
        
        # Acceptance threshold: start at 30%, converge to 20% near end
        # Accept if we get a reasonable share
        min_accept = self.total * (0.30 - 0.10 * progress)
        if my_value >= min_accept:
            return None
        
        # If this is last chance and we have a decent offer, accept it
        if self.turn >= self.total_turns - 1 and self.best_received_value > 0:
            return None
        
        # Counteroffer: start at 48%, gradually concede
        target_pct = 0.48 - 0.15 * progress
        target = int(self.total * target_pct)
        
        # Ensure we don't ask for more than opponent can give
        target = min(target, self.total - int(self.total * 0.20))
        
        return self._make_offer(target)
    
    def _make_offer(self, target: int) -> list[int]:
        # Sort by value descending - take most valuable items first
        indices = sorted(range(len(self.values)), 
                        key=lambda i: self.values[i], reverse=True)
        
        offer = [0] * len(self.counts)
        remaining = self.counts.copy()
        
        # Take items greedily until target
        for idx in indices:
            while remaining[idx] > 0 and self._value(offer) + self.values[idx] <= target:
                offer[idx] += 1
                remaining[idx] -= 1
        
        # Take remaining items we can get
        for idx in indices:
            while remaining[idx] > 0:
                offer[idx] += 1
                remaining[idx] -= 1
        
        return offer