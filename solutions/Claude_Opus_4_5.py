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
        self.last_offer = None
        
    def _value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _generate_splits(self):
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
    
    def _estimate_opponent_values(self) -> list[float]:
        """Estimate opponent values based on what they keep for themselves."""
        if not self.opponent_offers:
            # Start by assuming inverse correlation with our values
            base = [1.0 / (v + 1) for v in self.values]
        else:
            base = [0.0] * self.n
            for offer in self.opponent_offers:
                for i in range(self.n):
                    kept = self.counts[i] - offer[i]
                    if self.counts[i] > 0:
                        base[i] += kept / self.counts[i]
        
        total = sum(base) + 0.001
        return [b / total for b in base]
    
    def _find_best_offer(self, min_value: int, opp_weights: list[float]) -> list[int] | None:
        """Find offer that gives us min_value while maximizing opponent's estimated value."""
        splits = self._generate_splits()
        best, best_score = None, -float('inf')
        
        for split in splits:
            my_val = self._value(split)
            if my_val < min_value:
                continue
            
            # Score by what opponent gets (weighted)
            opp_score = sum((self.counts[i] - split[i]) * opp_weights[i] for i in range(self.n))
            # Slight preference for giving us more if opponent score is equal
            score = opp_score * 1000 + my_val
            
            if score > best_score:
                best_score = score
                best = list(split)
        return best
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = 2 * self.max_rounds
        remaining = total_turns - self.turn
        progress = self.turn / total_turns
        
        if o is not None:
            self.opponent_offers.append(o)
            offer_val = self._value(o)
            
            # Accept conditions - be more demanding early, flexible late
            if remaining == 0:  # Last turn
                return None if offer_val > 0 else list(self.counts)
            
            # Graduated acceptance threshold
            if progress < 0.3:
                threshold = 0.60 * self.total
            elif progress < 0.6:
                threshold = 0.50 * self.total
            elif progress < 0.85:
                threshold = 0.40 * self.total
            else:
                threshold = 0.30 * self.total
            
            if offer_val >= threshold:
                return None
        
        opp_weights = self._estimate_opponent_values()
        
        # Demand curve - start very high, decrease gradually
        if progress < 0.25:
            demand = 0.85 * self.total
        elif progress < 0.5:
            demand = 0.70 * self.total
        elif progress < 0.75:
            demand = 0.55 * self.total
        else:
            demand = 0.40 * self.total
        
        target = max(1, int(demand))
        result = self._find_best_offer(target, opp_weights)
        
        # Fallback with lower demands
        for fallback in [0.35, 0.25, 0.15, 0.01]:
            if result is None:
                result = self._find_best_offer(max(1, int(self.total * fallback)), opp_weights)
        
        if result is None:
            result = list(self.counts)
        
        self.last_offer = result
        return result