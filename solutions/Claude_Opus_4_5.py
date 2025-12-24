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
        self.best_offer_received = None
        self.best_offer_value = 0
        
    def _value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _opponent_gets(self, offer: list[int]) -> list[int]:
        return [self.counts[i] - offer[i] for i in range(self.n)]
    
    def _infer_opponent_values(self) -> list[float]:
        """Infer opponent values based on what they consistently want to keep."""
        if len(self.opponent_offers) < 2:
            # Start with assumption: inverse correlation with our values
            return [1.0 / (v + 0.5) for v in self.values]
        
        # Score how much opponent wants each item type (higher = wants more)
        scores = [0.0] * self.n
        for offer in self.opponent_offers:
            opp_keeps = self._opponent_gets(offer)
            for i in range(self.n):
                if self.counts[i] > 0:
                    scores[i] += opp_keeps[i] / self.counts[i]
        
        # Normalize to sum to total (assume same total value)
        total_score = sum(scores) + 0.001
        return [s / total_score * self.total / max(1, self.counts[i]) 
                for i, s in enumerate(scores)]
    
    def _score_for_opponent(self, offer: list[int], opp_vals: list[float]) -> float:
        opp_gets = self._opponent_gets(offer)
        return sum(opp_gets[i] * opp_vals[i] * self.counts[i] for i in range(self.n))
    
    def _generate_all_offers(self) -> list[list[int]]:
        """Generate all possible offers."""
        offers = []
        def gen(idx, current):
            if idx == self.n:
                offers.append(list(current))
                return
            for c in range(self.counts[idx] + 1):
                current.append(c)
                gen(idx + 1, current)
                current.pop()
        gen(0, [])
        return offers
    
    def _find_pareto_optimal_offer(self, min_value: int, progress: float) -> list[int]:
        """Find offer that maximizes opponent value while meeting our minimum."""
        all_offers = self._generate_all_offers()
        opp_vals = self._infer_opponent_values()
        
        # Filter offers meeting our minimum
        valid = [(off, self._value(off), self._score_for_opponent(off, opp_vals)) 
                 for off in all_offers if self._value(off) >= min_value]
        
        if not valid:
            # Return best offer for us
            return max(all_offers, key=lambda x: self._value(x))
        
        # Sort by opponent value (descending), then our value (descending)
        valid.sort(key=lambda x: (x[2], x[1]), reverse=True)
        return valid[0][0]
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = 2 * self.max_rounds
        remaining = total_turns - self.turn
        progress = self.turn / total_turns
        
        if o is not None:
            self.opponent_offers.append(o)
            offer_val = self._value(o)
            
            # Track best offer
            if offer_val > self.best_offer_value:
                self.best_offer_value = offer_val
                self.best_offer_received = o
            
            # Acceptance logic
            # Last turn: accept anything positive
            if remaining == 0:
                return None if offer_val > 0 else self._find_pareto_optimal_offer(1, 1.0)
            
            # Dynamic threshold based on progress
            if progress < 0.3:
                threshold = self.total * 0.45
            elif progress < 0.6:
                threshold = self.total * 0.35
            elif progress < 0.85:
                threshold = self.total * 0.25
            else:
                threshold = self.total * 0.15
            
            # Accept if meets threshold
            if offer_val >= threshold:
                return None
            
            # Near end: accept best offer we've seen if reasonable
            if progress > 0.8 and self.best_offer_value >= self.total * 0.2:
                if offer_val >= self.best_offer_value * 0.9:
                    return None
        
        # Generate counter-offer
        # Start ambitious, become more generous
        if progress < 0.25:
            target = self.total * 0.55
        elif progress < 0.5:
            target = self.total * 0.45
        elif progress < 0.75:
            target = self.total * 0.35
        else:
            target = self.total * 0.25
        
        target = max(1, int(target))
        return self._find_pareto_optimal_offer(target, progress)