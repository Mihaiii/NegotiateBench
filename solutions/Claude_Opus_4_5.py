class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.me = me
        self.turn = 0
        self.n = len(counts)
        self.opponent_offers = []
        self.my_offers = []
        self.all_splits = self._generate_splits()
        
    def _value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _generate_splits(self) -> list[tuple]:
        splits = []
        def gen(idx, current):
            if idx == self.n:
                splits.append(tuple(current))
                return
            for c in range(self.counts[idx] + 1):
                current.append(c)
                gen(idx + 1, current)
                current.pop()
        gen(0, [])
        return splits
    
    def _estimate_opponent_value(self, offer: list[int]) -> float:
        """Estimate what opponent gets from an offer (what they keep)."""
        if not self.opponent_offers:
            # Assume inverse correlation initially
            weights = [1.0 / (v + 0.1) for v in self.values]
        else:
            # Track what items opponent consistently wants
            weights = [0.1] * self.n
            for opp_offer in self.opponent_offers:
                for i in range(self.n):
                    kept = self.counts[i] - opp_offer[i]
                    weights[i] += kept
        
        total_w = sum(weights) + 0.001
        weights = [w / total_w for w in weights]
        
        opp_gets = sum((self.counts[i] - offer[i]) * weights[i] for i in range(self.n))
        return opp_gets
    
    def _best_offer_for_value(self, min_val: int) -> list[int] | None:
        """Find offer giving us at least min_val while maximizing opponent's estimated value."""
        best, best_opp = None, -1
        for split in self.all_splits:
            my_val = self._value(split)
            if my_val >= min_val:
                opp_val = self._estimate_opponent_value(list(split))
                if opp_val > best_opp or (opp_val == best_opp and (best is None or my_val > self._value(best))):
                    best_opp = opp_val
                    best = list(split)
        return best
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = 2 * self.max_rounds
        remaining = total_turns - self.turn
        is_last = remaining == 0
        progress = self.turn / total_turns
        
        if o is not None:
            self.opponent_offers.append(o)
            offer_val = self._value(o)
            
            # Always accept something positive on last turn
            if is_last:
                return None if offer_val > 0 else list(self.counts)
            
            # Dynamic acceptance: accept if offer is good enough given remaining time
            # Be more accepting as time runs out
            accept_threshold = self.total * max(0.15, 0.55 - 0.45 * progress)
            
            # Also accept if opponent improved their offer significantly
            if len(self.opponent_offers) >= 2:
                prev_val = self._value(self.opponent_offers[-2])
                if offer_val > prev_val and offer_val >= self.total * 0.35:
                    accept_threshold = min(accept_threshold, offer_val)
            
            if offer_val >= accept_threshold:
                return None
        
        # Determine demand level based on progress
        # Start high, gradually decrease, with some randomization via turn
        base_demand = 0.75 - 0.45 * progress
        demand = max(0.2, base_demand)
        target = max(1, int(self.total * demand))
        
        result = self._best_offer_for_value(target)
        
        # Fallback to lower demands if needed
        while result is None and target > 0:
            target = int(target * 0.8)
            result = self._best_offer_for_value(target)
        
        if result is None:
            result = list(self.counts)
        
        # Avoid repeating exact same offer too many times - try slight variations
        if self.my_offers and len(self.my_offers) >= 3:
            if all(self.my_offers[-i] == result for i in range(1, min(4, len(self.my_offers)+1))):
                # Try a slightly lower demand
                alt = self._best_offer_for_value(max(1, int(target * 0.85)))
                if alt and alt != result:
                    result = alt
        
        self.my_offers.append(result)
        return result