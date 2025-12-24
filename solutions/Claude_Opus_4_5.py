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
    
    def _opponent_keeps(self, offer: list[int]) -> list[int]:
        return [self.counts[i] - offer[i] for i in range(self.n)]
    
    def _infer_opponent_values(self) -> list[float]:
        """Infer opponent's relative values from their offer patterns."""
        weights = [1.0] * self.n
        
        for opp_offer in self.opponent_offers:
            opp_keeps = self._opponent_keeps(opp_offer)
            for i in range(self.n):
                if self.counts[i] > 0:
                    keep_ratio = opp_keeps[i] / self.counts[i]
                    weights[i] += keep_ratio * 2
        
        # Normalize
        total_w = sum(weights) + 0.001
        return [w / total_w for w in weights]
    
    def _score_offer_for_opponent(self, offer: list[int]) -> float:
        """Estimate how good an offer is for opponent."""
        opp_weights = self._infer_opponent_values()
        opp_keeps = self._opponent_keeps(offer)
        return sum(opp_keeps[i] * opp_weights[i] * self.counts[i] for i in range(self.n))
    
    def _generate_offers_by_value(self) -> list[tuple[list[int], int]]:
        """Generate all possible offers sorted by our value (descending)."""
        offers = []
        def gen(idx, current):
            if idx == self.n:
                offers.append((list(current), self._value(current)))
                return
            for c in range(self.counts[idx] + 1):
                current.append(c)
                gen(idx + 1, current)
                current.pop()
        gen(0, [])
        offers.sort(key=lambda x: (-x[1], -self._score_offer_for_opponent(x[0])))
        return offers
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = 2 * self.max_rounds
        remaining = total_turns - self.turn
        is_last = remaining == 0
        progress = self.turn / total_turns
        
        if o is not None:
            self.opponent_offers.append(o)
            offer_val = self._value(o)
            
            # On last turn, accept anything positive
            if is_last:
                return None if offer_val > 0 else list(self.counts)
            
            # Be much more conservative - only accept good deals
            # Start requiring 60%, slowly drop to 30% at the end
            min_accept = self.total * max(0.25, 0.60 - 0.40 * progress)
            
            if offer_val >= min_accept:
                return None
        
        # Generate demand based on progress - start very high
        all_offers = self._generate_offers_by_value()
        
        # Target value: start at 85% of total, end at ~35%
        target_ratio = max(0.30, 0.85 - 0.55 * progress)
        target_val = int(self.total * target_ratio)
        
        # Find best offer at or above target that's good for opponent
        best = None
        best_opp_score = -1
        for off, val in all_offers:
            if val >= target_val:
                opp_score = self._score_offer_for_opponent(off)
                if opp_score > best_opp_score:
                    best_opp_score = opp_score
                    best = off
        
        if best is None:
            best = all_offers[0][0] if all_offers else list(self.counts)
        
        self.my_offers.append(best)
        return best