class Agent:
    def __init__(self, me, counts, values, max_rounds):
        self.me = me
        self.counts = list(counts)
        self.values = list(values)
        self.n = len(counts)
        self.total_turns = max_rounds * 2
        self.turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Initialize opponent value estimates (uniform prior)
        total_items = sum(counts)
        if total_items > 0:
            avg = self.total_value / total_items
            self.opp_values = [avg] * self.n
        else:
            self.opp_values = [0] * self.n
        
    def offer(self, o):
        self.turn += 1
        remaining = self.total_turns - self.turn
        
        if o is not None:
            self._update_opponent_model(o)
            my_value = sum(x * v for x, v in zip(o, self.values))
            
            # Acceptance strategy: threshold decreases from 75% to 25% as time passes
            # Last turn: accept anything > 0
            if remaining == 0:
                if my_value > 0:
                    return None
            else:
                progress = self.turn / self.total_turns
                threshold = self.total_value * (0.75 - 0.50 * progress)
                if my_value >= threshold:
                    return None
        
        return self._create_offer()
    
    def _update_opponent_model(self, o):
        """Update opponent value estimates based on their offer."""
        # Opponent offers us 'o', keeps (counts - o)
        kept = [self.counts[i] - o[i] for i in range(self.n)]
        
        for i in range(self.n):
            if self.counts[i] == 0:
                continue
                
            give_ratio = o[i] / self.counts[i]
            keep_ratio = kept[i] / self.counts[i]
            
            # If they give us items, they likely value them less
            # If they keep items, they likely value them more
            current = self.opp_values[i]
            
            if give_ratio == 1.0:
                inferred = 0  # They gave all -> value is 0
            elif keep_ratio == 1.0:
                inferred = self.total_value / self.n  # They kept all -> value is high
            else:
                # Linear interpolation based on keep/give ratio
                inferred = (self.total_value / self.n) * (0.5 + 0.5 * (keep_ratio - give_ratio))
            
            # Smooth update
            self.opp_values[i] = 0.7 * current + 0.3 * inferred
        
        # Normalize to maintain total value constraint
        curr_total = sum(v * c for v, c in zip(self.opp_values, self.counts))
        if curr_total > 0:
            scale = self.total_value / curr_total
            self.opp_values = [v * scale for v in self.opp_values]
    
    def _create_offer(self):
        """Generate offer using constrained optimization."""
        progress = self.turn / self.total_turns if self.total_turns > 0 else 1
        
        # Assume opponent wants at least reservation value (decreasing from 75% to 25%)
        opp_reservation = self.total_value * (0.75 - 0.50 * progress)
        
        # Budget: how much value can we "take" from opponent without making them reject
        budget = self.total_value - opp_reservation
        
        # Sort items by efficiency: our_value / opponent_value
        # Take items that give us high value while costing opponent low value
        items = []
        for i in range(self.n):
            ov = self.opp_values[i]
            mv = self.values[i]
            if ov <= 0:
                efficiency = float('inf') if mv > 0 else 0
            else:
                efficiency = mv / ov
            items.append((efficiency, i, mv, ov))
        
        # Sort descending by efficiency
        items.sort(reverse=True)
        
        take = [0] * self.n
        
        for efficiency, i, mv, ov in items:
            if budget <= 0 and ov > 0:
                break
                
            if mv <= 0:
                continue  # Don't take worthless items
            
            if ov == 0:
                # Take all items that cost opponent nothing
                take[i] = self.counts[i]
            else:
                # Take as many as budget allows
                max_take = int(budget // ov)
                amt = min(self.counts[i], max_take)
                if amt > 0:
                    take[i] = amt
                    budget -= amt * ov
        
        # Ensure we offer a valid partition (all items accounted for)
        # The opponent gets (counts - take), which is implicit in the protocol
        return take