class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.me = me
        self.turn = 0
        self.n_items = len(counts)
        self.total_turns = 2 * max_rounds
        self.opponent_offers = []
        # Infer opponent preferences from their offers
        self.opp_value_estimate = [1.0] * self.n_items
        
    def _my_value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _update_opponent_model(self, opp_offer: list[int]):
        """Estimate opponent values based on what they give us less of."""
        for i in range(self.n_items):
            opp_keeps = self.counts[i] - opp_offer[i]
            if self.counts[i] > 0:
                keep_ratio = opp_keeps / self.counts[i]
                self.opp_value_estimate[i] = 0.6 * self.opp_value_estimate[i] + 0.4 * (keep_ratio * 10)

    def _estimated_opp_value(self, my_offer: list[int]) -> float:
        """Estimate what opponent gets from a deal where I get my_offer."""
        return sum((self.counts[i] - my_offer[i]) * self.opp_value_estimate[i] 
                   for i in range(self.n_items))

    def _generate_offers(self, min_value: int):
        """Generate all possible offers meeting minimum value."""
        offers = []
        def gen(idx, current, cur_val):
            if idx == self.n_items:
                if cur_val >= min_value:
                    offers.append((current.copy(), cur_val))
                return
            for c in range(self.counts[idx] + 1):
                new_val = cur_val + c * self.values[idx]
                if new_val + sum(self.counts[j] * self.values[j] for j in range(idx+1, self.n_items)) >= min_value:
                    current.append(c)
                    gen(idx + 1, current, new_val)
                    current.pop()
        gen(0, [], 0)
        return offers

    def _best_offer(self, min_value: int) -> list[int]:
        """Find offer meeting min_value that maximizes opponent's estimated value."""
        offers = self._generate_offers(min_value)
        if not offers:
            # Fallback: take everything valuable
            return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n_items)]
        
        # Sort by opponent's estimated satisfaction (descending), then by our value (descending)
        offers.sort(key=lambda x: (self._estimated_opp_value(x[0]), x[1]), reverse=True)
        return offers[0][0]

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        turns_left = self.total_turns - self.turn
        progress = self.turn / self.total_turns
        
        if o is not None:
            self.opponent_offers.append(o)
            self._update_opponent_model(o)
            my_val = self._my_value(o)
            
            # Last turn: accept anything positive
            if turns_left == 0:
                return None if my_val > 0 else self._best_offer(1)
            
            # Acceptance threshold: start at 55%, decrease to 35% near end
            min_accept = self.total * max(0.35, 0.55 - 0.25 * progress)
            
            if my_val >= min_accept:
                return None
        
        # Demand: start at 75%, decrease to 40%
        demand = self.total * max(0.40, 0.75 - 0.45 * progress)
        target = max(1, int(demand))
        
        return self._best_offer(target)