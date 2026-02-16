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
        avg_value = self.total_value / total_items if total_items > 0 else 0
        self.opp_values = [avg_value] * self.n
        
    def offer(self, o):
        self.turn += 1
        remaining = self.total_turns - self.turn
        is_last = (remaining == 0)
        
        if o is not None:
            self._update_model(o)
            offer_val = sum(a * b for a, b in zip(o, self.values))
            if self._should_accept(offer_val, is_last, remaining):
                return None
        
        return self._create_offer(is_last, remaining)
    
    def _update_model(self, o):
        """Update opponent value estimates based on kept vs given."""
        for i in range(self.n):
            if self.counts[i] == 0:
                continue
            
            given = o[i]  # Given to us
            kept = self.counts[i] - given  # Kept by them
            
            # If they keep more, they value it higher
            keep_ratio = kept / self.counts[i]
            
            # Estimate: assume they want to maximize, so keeping implies higher value
            # Scale by current total to maintain normalization
            if self.values[i] > 0:
                # Infer value relative to ours based on keep ratio
                inferred = self.values[i] * (0.5 + 1.5 * keep_ratio)
            else:
                inferred = self.total_value / self.n * keep_ratio
            
            # Exponential smoothing
            self.opp_values[i] = 0.7 * self.opp_values[i] + 0.3 * inferred
        
        # Normalize to ensure opponent total value sums to roughly same as ours
        current_total = sum(self.opp_values[i] * self.counts[i] for i in range(self.n))
        if current_total > 0:
            scale = self.total_value / current_total
            self.opp_values = [v * scale for v in self.opp_values]
    
    def _should_accept(self, offer_val, is_last, remaining):
        """Accept if offer meets decreasing threshold."""
        if is_last:
            return offer_val > 0
        
        # Threshold decreases from 70% to 30% as time progresses
        progress = self.turn / self.total_turns if self.total_turns > 0 else 0
        threshold = self.total_value * (0.70 - 0.40 * progress)
        
        # More lenient in final rounds
        if remaining <= 2:
            threshold = max(threshold, self.total_value * 0.25)
        
        return offer_val >= threshold
    
    def _create_offer(self, is_last, remaining):
        """Generate offer with concession strategy."""
        # Target decreases from 75% to 35% of total value
        if is_last:
            target = self.total_value * 0.35
        else:
            progress = self.turn / self.total_turns if self.total_turns > 0 else 0
            target = self.total_value * (0.75 - 0.40 * progress)
        
        take = [0] * self.n
        current_value = 0
        
        # First priority: items where my value > opponent estimate (win-win for me)
        win_items = [(self.values[i] - self.opp_values[i], self.values[i], i) 
                     for i in range(self.n) if self.values[i] > self.opp_values[i]]
        win_items.sort(reverse=True)
        
        for net, val, i in win_items:
            take[i] = self.counts[i]
            current_value += self.counts[i] * val
        
        # Second priority: if below target, take from remaining items by value density
        if current_value < target:
            # Sort remaining items by my value descending
            remaining_items = [(self.values[i], i) for i in range(self.n) if take[i] == 0 and self.values[i] > 0]
            remaining_items.sort(reverse=True)
            
            for val, i in remaining_items:
                if current_value >= target:
                    break
                
                need_val = target - current_value
                max_possible = self.counts[i] * val
                if max_possible <= need_val:
                    take[i] = self.counts[i]
                    current_value += max_possible
                else:
                    units = int((need_val + val - 1) // val)
                    take[i] = units
                    current_value += units * val
        
        # If we have nothing valuable, accept small offers but try to get something
        if current_value == 0 and target > 0:
            # Take at least one of the most valuable item we have
            best_idx = max(range(self.n), key=lambda i: self.values[i], default=-1)
            if best_idx >= 0 and self.values[best_idx] > 0:
                take[best_idx] = min(1, self.counts[best_idx])
        
        return take