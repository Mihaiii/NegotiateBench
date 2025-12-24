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
    
    def _opponent_gets(self, offer: list[int]) -> list[int]:
        return [self.counts[i] - offer[i] for i in range(self.n)]
    
    def _estimate_opponent_values(self) -> list[float]:
        """Estimate opponent's relative value for each item type."""
        if not self.opponent_offers:
            # Assume inverse of our values initially
            max_v = max(self.values) + 1
            return [max_v - v for v in self.values]
        
        # Count how much opponent wants to keep each item type
        want_scores = [0.0] * self.n
        for opp_offer in self.opponent_offers:
            opp_keeps = self._opponent_gets(opp_offer)
            for i in range(self.n):
                if self.counts[i] > 0:
                    want_scores[i] += opp_keeps[i] / self.counts[i]
        
        # Normalize
        total = sum(want_scores) + 0.001
        return [s / total * self.total for s in want_scores]
    
    def _score_offer_for_opponent(self, offer: list[int], opp_vals: list[float]) -> float:
        opp_gets = self._opponent_gets(offer)
        return sum(opp_gets[i] * opp_vals[i] for i in range(self.n))
    
    def _generate_offers_by_value(self) -> list[tuple[list[int], int]]:
        """Generate all valid offers sorted by our value descending."""
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
    
    def _find_best_offer(self, min_value: int) -> list[int]:
        """Find offer >= min_value that opponent likely accepts."""
        all_offers = self._generate_offers_by_value()
        candidates = [(off, val) for off, val in all_offers if val >= min_value]
        
        if not candidates:
            # Return best possible offer
            return all_offers[0][0] if all_offers else list(self.counts)
        
        opp_vals = self._estimate_opponent_values()
        # Pick offer that maximizes opponent's estimated value among valid ones
        best = max(candidates, key=lambda x: (self._score_offer_for_opponent(x[0], opp_vals), -x[1]))
        return best[0]
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = 2 * self.max_rounds
        remaining = total_turns - self.turn
        progress = self.turn / total_turns
        
        if o is not None:
            self.opponent_offers.append(o)
            offer_val = self._value(o)
            
            # Last turn - accept if positive
            if remaining == 0:
                return None if offer_val > 0 else self._find_best_offer(1)
            
            # Dynamic threshold: start ~50%, drop to ~20% near end
            threshold = self.total * max(0.15, 0.50 - 0.40 * progress)
            
            # Accept good offers, especially if better than what we've been offering
            if offer_val >= threshold:
                return None
            
            # Accept if opponent is being reasonable and we're running low on time
            if progress > 0.6 and offer_val >= self.total * 0.25:
                return None
        
        # Generate counter-offer
        # Start at ~65%, gradually reduce to ~25%
        target_ratio = max(0.20, 0.65 - 0.50 * progress)
        target_val = max(1, int(self.total * target_ratio))
        
        new_offer = self._find_best_offer(target_val)
        self.my_offers.append(new_offer)
        return new_offer