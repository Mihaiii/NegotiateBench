class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.me = me
        self.round = 0
        self.opponent_offers = []
        self.n_items = len(counts)
        
    def _my_value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _opponent_gets(self, my_offer: list[int]) -> list[int]:
        return [c - o for c, o in zip(self.counts, my_offer)]
    
    def _estimate_opponent_values(self) -> list[float]:
        """Estimate opponent values based on their offers."""
        if not self.opponent_offers:
            # Assume uniform distribution initially
            total_items = sum(self.counts)
            return [self.total / total_items] * self.n_items
        
        # Opponent wants items they value - look at what they want to keep
        scores = [0.0] * self.n_items
        for opp_offer in self.opponent_offers:
            opp_keeps = self._opponent_gets(opp_offer)
            for i in range(self.n_items):
                if self.counts[i] > 0:
                    scores[i] += opp_keeps[i] / self.counts[i]
        
        # Normalize to sum to total
        total_score = sum(scores)
        if total_score > 0:
            return [s / total_score * self.total for s in scores]
        return [self.total / self.n_items] * self.n_items
    
    def _generate_offers(self) -> list[list[int]]:
        """Generate all possible offers."""
        def generate(idx, current):
            if idx == self.n_items:
                yield current.copy()
                return
            for i in range(self.counts[idx] + 1):
                current.append(i)
                yield from generate(idx + 1, current)
                current.pop()
        return list(generate(0, []))
    
    def _find_best_offer(self, min_value: int, opp_values: list[float]) -> list[int] | None:
        """Find offer that maximizes opponent value while meeting my minimum."""
        best_offer = None
        best_opp_value = -1
        
        for offer in self._generate_offers():
            my_val = self._my_value(offer)
            if my_val >= min_value:
                opp_gets = self._opponent_gets(offer)
                opp_val = sum(o * v for o, v in zip(opp_gets, opp_values))
                if opp_val > best_opp_value:
                    best_opp_value = opp_val
                    best_offer = offer
        
        return best_offer
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is not None:
            self.opponent_offers.append(o)
        
        # Calculate current round (0-indexed)
        if self.me == 0:
            self.round = len(self.opponent_offers)
        else:
            self.round = len(self.opponent_offers) - 1 if self.opponent_offers else 0
        
        turns_left = 2 * self.max_rounds - (2 * self.round + (1 if self.me == 0 else 0))
        if o is not None:
            turns_left = 2 * self.max_rounds - len(self.opponent_offers) * 2 + 1
        
        # Calculate acceptance threshold based on remaining time
        progress = 1 - (turns_left / (2 * self.max_rounds))
        # Start wanting 70% of total, decrease to 35% as we run out of time
        min_acceptable = self.total * (0.70 - 0.35 * progress)
        
        # Check if we should accept
        if o is not None:
            my_val = self._my_value(o)
            # Accept if it meets our threshold or if it's the last round
            if my_val >= min_acceptable:
                return None
            # Accept anything positive on very last turn
            if turns_left <= 1 and my_val > 0:
                return None
        
        # Make a counter-offer
        opp_values = self._estimate_opponent_values()
        
        # Target value decreases as negotiations progress
        target = self.total * (0.75 - 0.30 * progress)
        
        best_offer = self._find_best_offer(target, opp_values)
        if best_offer is None:
            best_offer = self._find_best_offer(min_acceptable * 0.9, opp_values)
        if best_offer is None:
            best_offer = self._find_best_offer(1, opp_values)
        
        return best_offer if best_offer else self.counts.copy()