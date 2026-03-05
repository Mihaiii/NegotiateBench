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
        self.last_my_offer_value = 0
        
    def _value(self, alloc: list[int]) -> int:
        return sum(a * v for a, v in zip(alloc, self.values))
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        # Progress from 0 to 1
        progress = (self.turn - 1) / max(1, self.total_turns - 1)
        
        # First turn - make initial offer
        if o is None:
            # Start with ~55% target, slightly aggressive
            target = int(self.total * 0.55)
            return self._make_offer(target)
        
        # Track best offer received
        my_value = self._value(o)
        if my_value > self.best_received_value:
            self.best_received_value = my_value
            self.best_received = o
        
        # Acceptance threshold: start at 40%, converge to 25%
        min_accept_pct = 0.40 - 0.15 * progress
        min_accept = int(self.total * min_accept_pct)
        
        # Calculate what our next counter-offer would give us
        next_target_pct = 0.52 - 0.12 * progress
        next_target = int(self.total * next_target_pct)
        next_offer = self._make_offer(next_target)
        next_offer_value = self._value(next_offer)
        
        # Accept if:
        # 1. Offer meets minimum threshold, OR
        # 2. It's better than what we'd get in our next counter-offer AND we're not too early
        if my_value >= min_accept or (my_value >= next_offer_value and progress > 0.1):
            return None
        
        # Last chance - accept best received if it's reasonable
        if self.turn >= self.total_turns - 1:
            if self.best_received_value > 0:
                return None
            # Otherwise make one final offer
            return self._make_offer(int(self.total * 0.30))
        
        # Make counter-offer: start at 52%, gradually concede
        target_pct = 0.52 - 0.12 * progress
        target = int(self.total * target_pct)
        
        # Don't go below 30% of total value
        target = max(target, int(self.total * 0.30))
        
        return self._make_offer(target)
    
    def _make_offer(self, target: int) -> list[int]:
        # Sort by value-to-count ratio descending to maximize value per item
        # Use value per item since all items of a type have same value
        indices = sorted(range(len(self.values)), 
                        key=lambda i: self.values[i], reverse=True)
        
        offer = [0] * len(self.counts)
        remaining = self.counts.copy()
        
        # Take items greedily until we reach target
        for idx in indices:
            while remaining[idx] > 0 and self._value(offer) + self.values[idx] <= target:
                offer[idx] += 1
                remaining[idx] -= 1
        
        # Return what we have - don't take more than target
        # This is the key fix - the old code took ALL remaining items
        return offer