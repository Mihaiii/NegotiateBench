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
        
    def _value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _opponent_gets(self, my_offer: list[int]) -> list[int]:
        return [self.counts[i] - my_offer[i] for i in range(self.n)]
    
    def _infer_opponent_values(self) -> list[float]:
        """Estimate opponent's relative value per item type."""
        if not self.opponent_offers:
            # Assume inverse of our values initially
            inv = [1.0 / (v + 0.1) for v in self.values]
            total_inv = sum(inv) + 0.01
            return [x / total_inv for x in inv]
        
        # Weight recent offers more heavily
        weights = [0.5 ** (len(self.opponent_offers) - i - 1) for i in range(len(self.opponent_offers))]
        kept_scores = [0.0] * self.n
        
        for w, offer in zip(weights, self.opponent_offers):
            for i in range(self.n):
                # What they keep = counts - what they offer us
                kept = self.counts[i] - offer[i]
                if self.counts[i] > 0:
                    kept_scores[i] += w * (kept / self.counts[i])
        
        total = sum(kept_scores) + 0.01
        return [k / total for k in kept_scores]
    
    def _generate_splits(self):
        """Generate all possible splits."""
        splits = []
        def gen(idx, current):
            if idx == self.n:
                splits.append(current.copy())
                return
            for c in range(self.counts[idx] + 1):
                current.append(c)
                gen(idx + 1, current)
                current.pop()
        gen(0, [])
        return splits
    
    def _find_offer(self, min_value: int, opp_prefs: list[float]) -> list[int] | None:
        """Find offer giving us at least min_value, maximizing opponent's estimated utility."""
        splits = self._generate_splits()
        best, best_score = None, (-1, -1)
        
        for split in splits:
            my_val = self._value(split)
            if my_val < min_value:
                continue
            
            opp_score = sum((self.counts[i] - split[i]) * opp_prefs[i] for i in range(self.n))
            score = (opp_score, -my_val)  # Maximize opponent value, minimize our greed
            
            if score > best_score:
                best_score = score
                best = split
        return best
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = 2 * self.max_rounds
        remaining = total_turns - self.turn
        is_last = remaining == 0
        
        if o is not None:
            self.opponent_offers.append(o)
            offer_val = self._value(o)
            
            # Accept if it's the last turn and we get something
            if is_last:
                return None if offer_val > 0 else [c for c in self.counts]  # Demand all if zero
            
            # Dynamic acceptance: be more lenient as rounds decrease
            base_threshold = 0.50 if self.me == 0 else 0.45
            decay = 0.35 * (self.turn / total_turns)
            threshold = self.total * max(0.20, base_threshold - decay)
            
            # Accept good offers earlier for efficiency
            if offer_val >= threshold:
                return None
        
        opp_prefs = self._infer_opponent_values()
        
        # Demand curve: start high, reduce over time
        if self.turn == 1:
            demand_frac = 0.80
        else:
            base_demand = 0.65
            decay = 0.40 * (self.turn / total_turns)
            demand_frac = max(0.25, base_demand - decay)
        
        target = max(1, int(self.total * demand_frac))
        result = self._find_offer(target, opp_prefs)
        
        # Fallback: find any positive value offer
        if result is None:
            result = self._find_offer(1, opp_prefs)
        
        if result is None:
            result = self.counts.copy()
        
        self.my_offers.append(result)
        return result