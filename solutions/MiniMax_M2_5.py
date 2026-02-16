class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.turn = 0
        self.total_turns = max_rounds * 2
        
    def _value(self, alloc: list[int]) -> int:
        return sum(a * v for a, v in zip(alloc, self.values))
    
    def _partner_gets(self, my_offer: list[int]) -> list[int]:
        return [c - m for c, m in zip(self.counts, my_offer)]
    
    def _make_offer(self, target_pct: float) -> list[int]:
        """Create an offer targeting a specific percentage of total value."""
        target = self.total * target_pct
        offer = [0] * len(self.counts)
        remaining = self.counts.copy()
        
        # Sort by value (highest first)
        indices = sorted(range(len(self.values)), 
                        key=lambda i: self.values[i], reverse=True)
        
        # Greedily add items to meet target
        for idx in indices:
            while remaining[idx] > 0 and self._value(offer) + self.values[idx] <= target:
                offer[idx] += 1
                remaining[idx] -= 1
        
        # If we didn't get enough value, try to add more items
        # even if we exceed target slightly
        for idx in indices:
            while remaining[idx] > 0:
                offer[idx] += 1
                remaining[idx] -= 1
                if self._value(offer) >= target:
                    break
            if self._value(offer) >= target:
                break
        
        return offer
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        remaining = self.total_turns - self.turn
        
        # First turn - make opening offer targeting 55%
        if o is None:
            return self._make_offer(0.55)
        
        # Calculate value from their offer
        my_value = self._value(o)
        
        # Adaptive acceptance threshold
        # Be more flexible: start at 35%, converge to 25% toward the end
        progress = self.turn / self.total_turns
        min_accept = self.total * (0.35 - 0.15 * progress)
        
        # Also accept if we're getting close to our target
        if my_value >= min_accept:
            return None
        
        # Generate counteroffer - converge from 55% to 50%
        target_pct = 0.55 - 0.05 * progress
        offer = self._make_offer(target_pct)
        
        return offer