class Agent:
    def __init__(self, me, counts, values, max_rounds):
        self.me = me
        self.counts = list(counts)
        self.values = list(values)
        self.n = len(counts)
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.total_turns = max_rounds * 2
        self.turn = 0
        
        # Initialize opponent values uniformly
        total_items = sum(counts)
        avg = self.total_value / total_items if total_items > 0 else 0
        self.opp_values = [avg] * self.n
        
    def offer(self, o):
        self.turn += 1
        remaining = self.total_turns - self.turn
        
        if o is not None:
            # Update model: opponent kept counts - o
            opp_kept = [self.counts[i] - o[i] for i in range(self.n)]
            self._update_model(opp_kept)
            
            my_val = sum(a * b for a, b in zip(o, self.values))
            
            # Last turn: accept anything > 0 (rejecting gives 0)
            if remaining == 0:
                return None
            
            # Accept if above decaying threshold (80% -> 20%)
            progress = self.turn / self.total_turns
            threshold = self.total_value * (0.8 - 0.6 * progress)
            if my_val >= threshold:
                return None
        
        return self._create_offer(remaining)
    
    def _update_model(self, opp_kept):
        """Update opponent value estimates based on what they kept."""
        for i in range(self.n):
            if self.counts[i] == 0:
                continue
            ratio = opp_kept[i] / self.counts[i]
            # Higher keep ratio implies higher value
            inferred = (self.total_value / self.n) * (0.2 + 0.8 * ratio)
            self.opp_values[i] = 0.7 * self.opp_values[i] + 0.3 * inferred
        
        # Normalize to maintain total value constraint
        curr_total = sum(self.opp_values[i] * self.counts[i] for i in range(self.n))
        if curr_total > 0:
            scale = self.total_value / curr_total
            self.opp_values = [v * scale for v in self.opp_values]
    
    def _create_offer(self, remaining):
        """Generate offer with time-dependent concession."""
        progress = self.turn / self.total_turns if self.total_turns > 0 else 1
        # Target decreases from 85% to 25% of total value
        target = self.total_value * (0.85 - 0.60 * progress)
        
        take = [0] * self.n
        curr_val = 0
        
        # Sort by surplus (my value - opp value) descending
        items = [(self.values[i] - self.opp_values[i], self.values[i], i) 
                 for i in range(self.n)]
        items.sort(reverse=True)
        
        for surplus, val, i in items:
            if curr_val >= target:
                break
            if surplus > 0 and val > 0:
                # Take all items where I have comparative advantage
                take[i] = self.counts[i]
                curr_val += take[i] * val
        
        # If below target, take from remaining by my value density
        if curr_val < target:
            remaining_items = [(self.values[i], i) for i in range(self.n) if take[i] == 0 and self.values[i] > 0]
            remaining_items.sort(reverse=True)
            
            for val, i in remaining_items:
                if curr_val >= target:
                    break
                need = (target - curr_val) / val
                # Round up to ensure we meet target
                amt = min(self.counts[i], int(need) + (1 if need % 1 > 0 else 0))
                take[i] = amt
                curr_val += amt * val
        
        # Ensure we're not offering to take items we don't value when opponent might accept less
        # (Greedy is fine here)
        return take