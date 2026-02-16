class Agent:
    def __init__(self, me, counts, values, max_rounds):
        self.me = me
        self.counts = list(counts)
        self.values = list(values)
        self.n = len(counts)
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Initialize opponent values with uniform prior
        total_items = sum(counts)
        if total_items > 0:
            avg = self.total_value / total_items
            self.opp_values = [avg] * self.n
        else:
            self.opp_values = [0] * self.n
        
        # Track opponent offers to detect patterns
        self.opp_history = []
    
    def offer(self, o):
        self.turn += 1
        remaining = self.total_turns - self.turn
        
        if o is not None:
            self.opp_history.append(list(o))
            self._update_model(o)
            
            my_value = sum(a * b for a, b in zip(o, self.values))
            
            # Acceptance strategy with time decay
            if remaining == 0:
                # Last possible turn - accept anything positive
                if my_value > 0:
                    return None
            else:
                # Threshold decays from 65% to 15% as time progresses
                progress = self.turn / self.total_turns
                threshold = self.total_value * (0.65 - 0.50 * progress)
                
                if my_value >= threshold:
                    return None
                
                # Late game: accept if we get at least 35%
                if progress > 0.75 and my_value >= self.total_value * 0.35:
                    return None
        
        return self._create_offer(remaining)
    
    def _update_model(self, o):
        """Update opponent value estimates based on their offer."""
        # Opponent keeps (counts - o), offers us o
        kept = [self.counts[i] - o[i] for i in range(self.n)]
        
        for i in range(self.n):
            if self.counts[i] == 0:
                continue
            
            give_frac = o[i] / self.counts[i]
            keep_frac = kept[i] / self.counts[i]
            
            # Infer value: keeping all -> high value, giving all -> low value
            if give_frac >= 0.99:
                inferred = 0
            elif keep_frac >= 0.99:
                inferred = self.total_value / self.n * 1.5
            else:
                # Linear interpolation based on keep/give ratio
                base = self.total_value / self.n
                inferred = base * (0.5 + (keep_frac - give_frac))
                inferred = max(0, inferred)
            
            # Exponential smoothing
            self.opp_values[i] = 0.7 * self.opp_values[i] + 0.3 * inferred
        
        # Renormalize to maintain total value constraint
        curr_total = sum(v * c for v, c in zip(self.opp_values, self.counts))
        if curr_total > 0:
            scale = self.total_value / curr_total
            self.opp_values = [v * scale for v in self.opp_values]
    
    def _create_offer(self, remaining):
        """Generate offer using comparative advantage and concession strategy."""
        # Target value decreases from 80% to 40% as we concede over time
        progress = self.turn / self.total_turns if self.total_turns > 0 else 1
        target_ratio = 0.80 - 0.40 * progress
        target_value = self.total_value * max(0.40, target_ratio)
        
        # Sort items by comparative advantage (our value - their estimated value)
        # High advantage = we should take it (we value it more)
        items = []
        for i in range(self.n):
            advantage = self.values[i] - self.opp_values[i]
            items.append((advantage, self.values[i], i))
        
        # Sort descending by advantage
        items.sort(reverse=True)
        
        take = [0] * self.n
        current_value = 0
        
        # First pass: take all items with positive advantage that have value to us
        for advantage, my_val, i in items:
            if advantage >= 0 and my_val > 0:
                take[i] = self.counts[i]
                current_value += take[i] * my_val
        
        # If we already exceed target, don't be greedy with marginal items
        if current_value >= target_value:
            return take
        
        # Second pass: take from neutral/negative advantage items if needed to reach target
        for advantage, my_val, i in items:
            if current_value >= target_value:
                break
            if take[i] > 0 or my_val <= 0:
                continue
            
            needed = target_value - current_value
            count_needed = int(needed / my_val) + 1
            amt = min(count_needed, self.counts[i])
            take[i] = amt
            current_value += amt * my_val
        
        return take