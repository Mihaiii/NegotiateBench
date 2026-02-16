class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.turn = 0
        self.total_turns = max_rounds * 2
        self.offers_made = []
        
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
        
        # Ensure we get something if target is above 0
        if self._value(offer) == 0 and target > 0:
            for idx in indices:
                if self.counts[idx] > 0 and self.values[idx] > 0:
                    offer[idx] = min(1, self.counts[idx])
                    break
        
        return offer
    
    def _generate_diverse_offer(self, target_pct: float, variation: int) -> list[int]:
        """Generate offer with variation to avoid repeating same offer."""
        # Try different item combinations for same target
        target = self.total * target_pct
        best = None
        best_val = -1
        
        # Try multiple random-ish approaches
        for seed in range(20):
            offer = [0] * len(self.counts)
            remaining = self.counts.copy()
            
            # Shuffle indices with different seeds
            indices = sorted(range(len(self.values)), 
                           key=lambda i: (self.values[i] * (seed + 1) + i * seed) % 17, 
                           reverse=True)
            
            for idx in indices:
                while remaining[idx] > 0 and self._value(offer) + self.values[idx] <= target:
                    offer[idx] += 1
                    remaining[idx] -= 1
            
            val = self._value(offer)
            if val > best_val and val <= target:
                best = offer
                best_val = val
        
        if best is None:
            return self._make_offer(target_pct)
        return best
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        remaining = self.total_turns - self.turn
        
        # First turn - make opening offer targeting 45%
        if o is None:
            offer = self._generate_diverse_offer(0.45, 0)
            self.offers_made.append(tuple(offer))
            return offer
        
        # Calculate value from their offer
        my_value = self._value(o)
        
        # Adaptive acceptance threshold - be more willing to accept as time runs out
        # Early: need >45%, Late: accept anything >35%
        progress = self.turn / self.total_turns
        min_accept = self.total * (0.45 - 0.15 * progress)
        
        # Accept if we meet threshold
        if my_value >= min_accept:
            return None
        
        # Generate counteroffer converging toward ~50%
        # Start aggressive (45%) and gradually move toward 50% as we converge
        target_pct = min(0.45 + 0.10 * (1 - progress), 0.50)
        
        # Try to make a different offer than before
        for attempt in range(10):
            offer = self._generate_diverse_offer(target_pct, attempt)
            if tuple(offer) not in self.offers_made:
                self.offers_made.append(tuple(offer))
                return offer
        
        # If all variations used, just return any valid offer
        return self._generate_diverse_offer(target_pct, 0)