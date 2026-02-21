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
        
        # Initialize opponent values with uniform prior (average value per item)
        total_items = sum(counts)
        if total_items > 0:
            avg = self.total_value / total_items
            self.opp_values = [avg] * self.n
        else:
            self.opp_values = [0] * self.n
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        remaining = self.total_turns - self.turn
        
        # Process opponent offer
        if o is not None:
            my_value = sum(a * b for a, b in zip(o, self.values))
            
            # Acceptance strategy with time decay
            if remaining == 0:
                # Last possible turn - accept anything positive to avoid zero
                if my_value > 0:
                    return None
            else:
                # Threshold decays from 55% to 30% as time progresses
                progress = self.turn / self.total_turns
                threshold = self.total_value * (0.55 - 0.25 * progress)
                
                if my_value >= threshold:
                    return None
            
            # Update model based on opponent's offer
            self._update_model(o)
        
        # Generate counter-offer
        return self._create_offer(remaining)
    
    def _update_model(self, o: list[int]):
        """Update opponent value estimates based on their offer."""
        # Opponent keeps (counts - o), offers us o
        kept = [self.counts[i] - o[i] for i in range(self.n)]
        
        for i in range(self.n):
            if self.counts[i] == 0:
                continue
            
            keep_frac = kept[i] / self.counts[i]
            give_frac = o[i] / self.counts[i]
            
            # If they keep significantly more, they value it higher
            if keep_frac > give_frac + 0.1:
                self.opp_values[i] *= 1.15
            # If they give significantly more, they value it lower
            elif give_frac > keep_frac + 0.1:
                self.opp_values[i] *= 0.85
            
            # Ensure non-negative
            self.opp_values[i] = max(0.01, self.opp_values[i])
        
        # Renormalize to maintain total value constraint (both players have same total)
        curr_total = sum(v * c for v, c in zip(self.opp_values, self.counts))
        if curr_total > 0:
            scale = self.total_value / curr_total
            self.opp_values = [v * scale for v in self.opp_values]
    
    def _create_offer(self, remaining: int) -> list[int]:
        """Generate offer using comparative advantage and concession strategy."""
        # Calculate progress (0 to 1)
        progress = self.turn / self.total_turns if self.total_turns > 0 else 1
        
        # Target value decreases from 70% to 50% as we concede over time
        target_value = self.total_value * (0.70 - 0.20 * progress)
        
        # Sort items by comparative advantage (my value - estimated opponent value)
        # High positive = I value it much more than them (I should take it)
        # High negative = They value it much more (I should give it)
        items = []
        for i in range(self.n):
            advantage = self.values[i] - self.opp_values[i]
            items.append((advantage, self.values[i], i))
        
        # Sort descending by advantage
        items.sort(reverse=True, key=lambda x: x[0])
        
        take = [0] * self.n
        current_value = 0
        
        # First pass: take all items with positive comparative advantage
        for advantage, my_val, i in items:
            if advantage >= 0 and my_val > 0:
                take[i] = self.counts[i]
                current_value += take[i] * my_val
        
        # Second pass: if we haven't reached target, take from best remaining items
        # even if advantage is slightly negative (concession)
        if current_value < target_value:
            for advantage, my_val, i in items:
                if current_value >= target_value:
                    break
                if take[i] > 0 or my_val <= 0:
                    continue
                
                # Calculate how many we need to reach target
                needed = target_value - current_value
                count_needed = int(needed // my_val) + 1
                amt = min(count_needed, self.counts[i])
                
                take[i] = amt
                current_value += amt * my_val
        
        return take