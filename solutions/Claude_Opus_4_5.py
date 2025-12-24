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
        self.all_offers = self._precompute_offers()
        
    def _value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _opponent_gets(self, offer: list[int]) -> list[int]:
        return [self.counts[i] - offer[i] for i in range(self.n)]
    
    def _precompute_offers(self) -> list[tuple[list[int], int]]:
        """Generate all valid offers sorted by value descending."""
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
        offers.sort(key=lambda x: -x[1])
        return offers
    
    def _estimate_opponent_value(self, offer: list[int]) -> float:
        """Estimate opponent's value based on what they consistently want."""
        if not self.opponent_offers:
            return 0.5
        
        # Track what opponent keeps across offers
        keep_freq = [0.0] * self.n
        for opp_offer in self.opponent_offers:
            opp_keeps = self._opponent_gets(opp_offer)
            for i in range(self.n):
                if self.counts[i] > 0:
                    keep_freq[i] += opp_keeps[i] / self.counts[i]
        
        # Normalize by number of observations
        for i in range(self.n):
            keep_freq[i] /= len(self.opponent_offers)
        
        # Score what opponent gets in proposed offer
        opp_gets = self._opponent_gets(offer)
        score = sum(opp_gets[i] * keep_freq[i] for i in range(self.n))
        max_score = sum(self.counts[i] * keep_freq[i] for i in range(self.n))
        return score / (max_score + 0.001)
    
    def _find_best_offer(self, min_value: int) -> list[int]:
        """Find offer with at least min_value that's best for opponent."""
        candidates = [(off, val) for off, val in self.all_offers if val >= min_value]
        if not candidates:
            return self.all_offers[0][0] if self.all_offers else list(self.counts)
        
        # Among valid offers, pick one opponent likely values most
        best = max(candidates, key=lambda x: self._estimate_opponent_value(x[0]))
        return best[0]
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = 2 * self.max_rounds
        remaining = total_turns - self.turn
        progress = self.turn / total_turns
        
        if o is not None:
            self.opponent_offers.append(o)
            offer_val = self._value(o)
            
            # Accept on last turn if positive value
            if remaining == 0:
                return None if offer_val > 0 else self._find_best_offer(1)
            
            # Dynamic acceptance threshold
            # Start at 55% of total, decrease to 25% near end
            threshold = self.total * max(0.20, 0.55 - 0.35 * progress)
            
            # Accept if offer is good enough
            if offer_val >= threshold:
                return None
        
        # Generate counter-offer
        # Start demanding 75%, gradually reduce to 35%
        target_ratio = max(0.30, 0.75 - 0.50 * progress)
        target_val = max(1, int(self.total * target_ratio))
        
        return self._find_best_offer(target_val)