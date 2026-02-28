class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = list(counts)
        self.values = list(values)
        self.n = len(counts)
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Initialize opponent values with my values (neutral prior)
        self.opp_values = list(values)
        self.last_offer = None
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        remaining = self.total_turns - self.turn
        
        if o is not None:
            my_val = sum(a * b for a, b in zip(o, self.values))
            self._update_beliefs(o)
            
            if self._should_accept(my_val, remaining):
                return None
        
        offer = self._make_offer(remaining)
        self.last_offer = offer[:]
        return offer
    
    def _update_beliefs(self, o: list[int]):
        """Update opponent value estimates based on their offer."""
        if self.last_offer is None:
            return
            
        for i in range(self.n):
            keep_now = self.counts[i] - o[i]
            keep_before = self.counts[i] - self.last_offer[i]
            
            # If opponent keeps more of item i than we offered them, they value it higher
            if keep_now > keep_before:
                self.opp_values[i] *= 1.15
            elif keep_now < keep_before:
                self.opp_values[i] *= 0.9
                
        # Renormalize to maintain total value constraint
        curr_total = sum(v * c for v, c in zip(self.opp_values, self.counts))
        if curr_total > 0:
            scale = self.total_value / curr_total
            self.opp_values = [max(0.01, v * scale) for v in self.opp_values]
    
    def _should_accept(self, val: int, remaining: int) -> bool:
        """Determine if we should accept the offer."""
        if val == 0:
            return False
        if remaining == 0:
            return True
        
        # Acceptance threshold decreases from 65% to 35% as deadline approaches
        progress = (self.total_turns - remaining) / self.total_turns
        threshold = self.total_value * (0.65 - 0.30 * progress)
        return val >= threshold
    
    def _make_offer(self, remaining: int) -> list[int]:
        """Generate offer respecting comparative advantage."""
        # Calculate maximum efficient value (sum of items where I have higher valuation)
        efficient_val = sum(
            self.counts[i] * self.values[i] 
            for i in range(self.n) 
            if self.values[i] > self.opp_values[i]
        )
        
        # Target decreases from 85% to 50% of efficient value as we concede
        progress = (self.total_turns - remaining) / self.total_turns
        target = efficient_val * (0.85 - 0.35 * progress)
        
        # Sort items by comparative advantage (my_value - opp_value) descending
        items = list(range(self.n))
        items.sort(key=lambda i: self.values[i] - self.opp_values[i], reverse=True)
        
        offer = [0] * self.n
        current_val = 0
        
        for i in items:
            if self.values[i] == 0:
                continue  # Never take worthless items
            
            # Take all of this item
            offer[i] = self.counts[i]
            current_val += self.counts[i] * self.values[i]
            
            # Stop if we've reached target and next items have negative advantage
            if current_val >= target:
                # Check if remaining items have negative advantage
                next_adv = self.values[items[-1]] - self.opp_values[items[-1]] if len(items) > 0 else -1
                if i < len(items) - 1:
                    next_idx = items[items.index(i) + 1]
                    next_adv = self.values[next_idx] - self.opp_values[next_idx]
                if next_adv < 0:
                    break
        
        return offer