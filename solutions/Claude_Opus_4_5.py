class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.me = me
        self.turn = 0
        self.opponent_offers = []
        self.n_items = len(counts)
        self.total_turns = 2 * max_rounds
        self.all_offers = self._generate_all_offers()
        self.inferred_opp_values = [1] * self.n_items  # Start neutral
        
    def _my_value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _generate_all_offers(self) -> list[list[int]]:
        def generate(idx, current):
            if idx == self.n_items:
                yield tuple(current)
                return
            for i in range(self.counts[idx] + 1):
                current.append(i)
                yield from generate(idx + 1, current)
                current.pop()
        return [list(o) for o in generate(0, [])]
    
    def _update_opponent_model(self):
        """Infer opponent values from their offers."""
        if len(self.opponent_offers) < 2:
            return
        # Items opponent consistently keeps likely have high value to them
        for i in range(self.n_items):
            opp_keeps = [self.counts[i] - o[i] for o in self.opponent_offers]
            avg_keep = sum(opp_keeps) / len(opp_keeps)
            if self.counts[i] > 0:
                self.inferred_opp_values[i] = avg_keep / self.counts[i] * 10 + 0.1

    def _estimate_opp_value(self, my_offer: list[int]) -> float:
        """Estimate opponent's value for what they'd get."""
        return sum((self.counts[i] - my_offer[i]) * self.inferred_opp_values[i] 
                   for i in range(self.n_items))

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        if o is not None:
            self.opponent_offers.append(o)
            self._update_opponent_model()
        
        turns_remaining = self.total_turns - self.turn
        progress = self.turn / self.total_turns
        
        # Acceptance logic
        if o is not None:
            my_val = self._my_value(o)
            
            # Last turn - accept anything positive
            if turns_remaining == 0:
                return None if my_val > 0 else self._best_offer()
            
            # Dynamic threshold based on progress
            if turns_remaining <= 2:
                threshold = self.total * 0.25
            else:
                threshold = self.total * (0.6 - 0.35 * progress)
            
            if my_val >= threshold:
                return None
        
        # Generate counter-offer
        if turns_remaining <= 1:
            min_val = max(1, self.total * 0.2)
        elif turns_remaining <= 3:
            min_val = self.total * 0.35
        else:
            min_val = self.total * (0.65 - 0.30 * progress)
        
        # Find offer meeting our minimum that likely appeals to opponent
        best_offer = None
        best_score = -float('inf')
        
        for offer in self.all_offers:
            my_val = self._my_value(offer)
            if my_val >= min_val:
                opp_val = self._estimate_opp_value(offer)
                score = opp_val + my_val * 0.1  # Prefer offers opponent might like
                if score > best_score:
                    best_score = score
                    best_offer = offer
        
        return best_offer if best_offer else self._best_offer()
    
    def _best_offer(self) -> list[int]:
        return max(self.all_offers, key=self._my_value)