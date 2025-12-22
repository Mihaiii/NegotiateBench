class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.rounds_left = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.num_types = len(counts)
        self.opponent_offers = []
        self.my_offers = []
        
    def _my_value(self, offer: list[int]) -> int:
        """Calculate my value for an offer (what I get)."""
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _opponent_gets(self, my_share: list[int]) -> list[int]:
        """Calculate what opponent gets given my share."""
        return [c - m for c, m in zip(self.counts, my_share)]
    
    def _estimate_opponent_values(self) -> list[float]:
        """Estimate opponent's values based on their offers."""
        if not self.opponent_offers:
            # No info yet, assume uniform or inverse of mine
            base = [self.total / sum(self.counts)] * self.num_types
            return base
        
        # Opponent offers describe what I get, so they want counts - offer
        # Items they consistently give away are likely low value to them
        avg_given = [0.0] * self.num_types
        for offer in self.opponent_offers:
            for i in range(self.num_types):
                avg_given[i] += offer[i] / len(self.opponent_offers)
        
        # Items they give us more of are likely less valuable to them
        total_items = sum(self.counts)
        est_values = []
        for i in range(self.num_types):
            if self.counts[i] == 0:
                est_values.append(0.0)
            else:
                # Proportion they keep vs give
                kept_ratio = 1 - (avg_given[i] / self.counts[i])
                est_values.append(kept_ratio * self.total / max(1, sum(self.counts)))
        
        # Normalize to sum to total
        total_est = sum(est_values[i] * self.counts[i] for i in range(self.num_types))
        if total_est > 0:
            est_values = [v * self.total / total_est for v in est_values]
        
        return est_values
    
    def _generate_offer(self, min_value: int) -> list[int] | None:
        """Generate an offer that gives me at least min_value."""
        est_opp = self._estimate_opponent_values()
        
        best_offer = None
        best_opp_value = -1
        
        # Generate candidate offers using greedy approach
        # Sort items by my value density vs opponent's estimated value density
        items = []
        for i in range(self.num_types):
            for j in range(self.counts[i] + 1):
                pass
        
        # Try all possible allocations (with pruning for efficiency)
        def generate_allocations(idx, current, my_val):
            nonlocal best_offer, best_opp_value
            
            if idx == self.num_types:
                if my_val >= min_value:
                    opp_share = self._opponent_gets(current)
                    opp_val = sum(est_opp[i] * opp_share[i] for i in range(self.num_types))
                    if opp_val > best_opp_value:
                        best_opp_value = opp_val
                        best_offer = current.copy()
                return
            
            for take in range(self.counts[idx] + 1):
                current.append(take)
                new_val = my_val + take * self.values[idx]
                generate_allocations(idx + 1, current, new_val)
                current.pop()
        
        generate_allocations(0, [], 0)
        return best_offer
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is not None:
            self.opponent_offers.append(o)
            my_val = self._my_value(o)
            
            # Calculate acceptance threshold based on rounds left
            progress = 1 - (self.rounds_left / self.max_rounds)
            threshold = self.total * (0.6 - 0.2 * progress)  # 60% -> 40%
            
            # Accept if good enough or last round
            if my_val >= threshold or (self.rounds_left <= 1 and my_val > 0):
                return None
        
        self.rounds_left -= 0.5  # Each call is half a round
        
        # Determine minimum acceptable value for my offer
        progress = 1 - (self.rounds_left / self.max_rounds)
        target = self.total * (0.7 - 0.25 * progress)  # Start high, decrease
        
        offer = self._generate_offer(int(target))
        if offer is None:
            offer = self._generate_offer(1)
        if offer is None:
            offer = self.counts.copy()
            
        self.my_offers.append(offer)
        return offer