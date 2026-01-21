class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.n = len(counts)
        # History of what the opponent KEPT (counts - offered)
        self.opp_history = [] 

    def offer(self, o: list[int] | None) -> list[int] | None:
        # 1. Update History & Identify Turn
        if o is not None:
            # If they offered 'o', they kept 'counts - o'
            kept = [self.counts[i] - o[i] for i in range(self.n)]
            self.opp_history.append(kept)
        
        # Calculate global turn index (0-based)
        # Agent 0 acts on turns 0, 2, 4... | Agent 1 acts on 1, 3, 5...
        if self.me == 0:
            turn = len(self.opp_history) * 2
        else:
            turn = len(self.opp_history) * 2 - 1
            
        total_turns = self.max_rounds * 2
        remaining = total_turns - turn
        
        # 2. Acceptance Logic
        if o is not None:
            my_o_val = sum(o[i] * self.values[i] for i in range(self.n))
            
            # Endgame: Agent 1 (Last Mover) must accept any positive outcome at last turn
            if remaining <= 1:
                if my_o_val > 0:
                    return None
            
            # Reservation Value Curve (Time-Dependent)
            progress = turn / total_turns
            
            # Thresholds: start demanding, concede later
            if progress < 0.2: min_frac = 0.98
            elif progress < 0.5: min_frac = 0.85
            elif progress < 0.8: min_frac = 0.75
            elif progress < 0.95: min_frac = 0.60
            else: min_frac = 0.45 
            
            if my_o_val >= int(self.total_value * min_frac):
                return None

        # 3. Opponent Modeling
        # Estimate Opponent Weights based on what they keep.
        # Heuristic: Value ~ 1 + (Frequency_Kept)^2
        opp_weights = [1.0] * self.n
        if self.opp_history:
            n_obs = len(self.opp_history)
            kept_sums = [0] * self.n
            for h in self.opp_history:
                for i in range(self.n):
                    kept_sums[i] += h[i]
            
            for i in range(self.n):
                if self.counts[i] > 0:
                    # Normalized frequency they kept this item (0.0 to 1.0)
                    freq = kept_sums[i] / (n_obs * self.counts[i])
                    # Higher power increases sensitivity to their preferences
                    opp_weights[i] = 1.0 + 5.0 * (freq ** 2)

        # 4. Counter-Offer Generation
        # Determine Target Value for Me
        progress_next = (turn + 1) / total_turns
        
        if progress_next < 0.2: target_frac = 1.0
        elif progress_next < 0.4: target_frac = 0.95
        elif progress_next < 0.7: target_frac = 0.85
        elif progress_next < 0.9: target_frac = 0.75
        elif progress_next < 0.98: target_frac = 0.60
        else: target_frac = 0.50
        
        # Endgame: Agent 0 (Second to Last Mover) MUST offer something tempting
        if self.me == 0 and remaining <= 2:
            target_frac = min(target_frac, 0.55)
            
        target_v = self.total_value * target_frac
        
        # 5. Greedy Efficiency Heuristic (Knapsack Variant)
        # We want to KEEP items with high Ratio = MyValue / EstOppWeight
        # This finds Pareto-efficient splits relative to the estimated model.
        items = []
        for i in range(self.n):
            if self.values[i] == 0:
                # If value is 0 for me, ratio is 0. 
                # Lowest priority to keep -> First to give away.
                r = 0.0
            else:
                r = self.values[i] / opp_weights[i]
            
            # Treat items individually
            for _ in range(self.counts[i]):
                items.append({'i': i, 'v': self.values[i], 'r': r})
        
        # Sort Descending: High Ratio (Keep) -> Low Ratio (Give)
        items.sort(key=lambda x: x['r'], reverse=True)
        
        proposal = [0] * self.n
        current_v = 0
        
        for item in items:
            # Accumulate items until target value is met
            # Ignore 0-value items (they stay at end of list and are not added)
            if item['v'] > 0 and current_v < target_v:
                proposal[item['i']] += 1
                current_v += item['v']
                
        return proposal