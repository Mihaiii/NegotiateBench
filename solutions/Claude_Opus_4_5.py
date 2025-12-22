class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.num_types = len(counts)
        self.opponent_offers = []
        self.turn_count = 0
        
    def _my_value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _all_allocations(self):
        """Generate all possible allocations."""
        def generate(idx, current):
            if idx == self.num_types:
                yield current.copy()
                return
            for take in range(self.counts[idx] + 1):
                current.append(take)
                yield from generate(idx + 1, current)
                current.pop()
        yield from generate(0, [])
    
    def _estimate_opponent_values(self) -> list[float]:
        """Estimate opponent values based on what they give vs keep."""
        if not self.opponent_offers:
            # Assume inverse correlation with my values
            inv = [self.total - v * c if c > 0 else 0 for v, c in zip(self.values, self.counts)]
            total_inv = sum(inv)
            if total_inv > 0:
                return [i * self.total / total_inv for i in inv]
            return [self.total / sum(self.counts)] * self.num_types
        
        # Items they consistently give us are likely low value to them
        avg_given_ratio = [0.0] * self.num_types
        for offer in self.opponent_offers:
            for i in range(self.num_types):
                if self.counts[i] > 0:
                    avg_given_ratio[i] += offer[i] / self.counts[i] / len(self.opponent_offers)
        
        # Higher ratio given = lower value to opponent
        est = [(1 - r) for r in avg_given_ratio]
        total_est = sum(est[i] * self.counts[i] for i in range(self.num_types))
        if total_est > 0:
            return [e * self.total / total_est for e in est]
        return [self.total / sum(self.counts)] * self.num_types

    def _generate_offer(self, min_my_value: int, est_opp: list[float]) -> list[int] | None:
        """Find offer giving me at least min_my_value that maximizes opponent value."""
        best_offer = None
        best_opp_value = -1
        
        for alloc in self._all_allocations():
            my_val = self._my_value(alloc)
            if my_val >= min_my_value:
                opp_share = [c - a for c, a in zip(self.counts, alloc)]
                opp_val = sum(est_opp[i] * opp_share[i] for i in range(self.num_types))
                if opp_val > best_opp_value:
                    best_opp_value = opp_val
                    best_offer = alloc
        return best_offer

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_left = total_turns - self.turn_count + 1
        progress = self.turn_count / total_turns
        
        if o is not None:
            self.opponent_offers.append(o)
            my_val = self._my_value(o)
            
            # Dynamic acceptance threshold
            # Start at ~65% of total, decrease to ~35% by end
            base_threshold = self.total * (0.65 - 0.30 * progress)
            
            # Accept if value meets threshold
            if my_val >= base_threshold:
                return None
            
            # Accept any positive value in last turn
            if turns_left <= 1 and my_val > 0:
                return None
            
            # Accept 40%+ in last 2 turns
            if turns_left <= 2 and my_val >= self.total * 0.40:
                return None
            
            # Accept 45%+ in last 3 turns  
            if turns_left <= 3 and my_val >= self.total * 0.45:
                return None
        
        est_opp = self._estimate_opponent_values()
        
        # Target value decreases as negotiation progresses
        # Start wanting ~70%, end at ~50%
        target = self.total * (0.70 - 0.20 * progress)
        
        # Try to find mutually beneficial offer
        offer = self._generate_offer(int(target), est_opp)
        
        # If no offer found at target, gradually lower requirements
        if offer is None:
            for reduction in range(1, int(self.total) + 1):
                offer = self._generate_offer(int(target) - reduction, est_opp)
                if offer is not None:
                    break
        
        # Fallback: take all valuable items
        if offer is None:
            offer = [c if v > 0 else 0 for c, v in zip(self.counts, self.values)]
        
        return offer