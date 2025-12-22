class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.num_types = len(counts)
        self.opponent_offers = []
        self.my_offers = []
        self.turn_count = 0
        self.best_offer_value = 0
        
    def _my_value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _all_allocations(self):
        def generate(idx, current):
            if idx == self.num_types:
                yield tuple(current)
                return
            for take in range(self.counts[idx] + 1):
                current.append(take)
                yield from generate(idx + 1, current)
                current.pop()
        yield from generate(0, [])
    
    def _estimate_opponent_values(self) -> list[float]:
        if not self.opponent_offers:
            # Initially assume inverse correlation with our values
            inv = [self.counts[i] - (self.values[i] / max(1, self.total) * self.counts[i]) 
                   for i in range(self.num_types)]
            total_inv = sum(inv)
            if total_inv > 0:
                return [i * self.total / total_inv for i in inv]
            return [self.total / max(1, sum(self.counts))] * self.num_types
        
        # Analyze what opponent keeps (doesn't give us)
        kept_ratios = [0.0] * self.num_types
        for offer in self.opponent_offers:
            for i in range(self.num_types):
                if self.counts[i] > 0:
                    kept_ratios[i] += (self.counts[i] - offer[i]) / self.counts[i]
        
        for i in range(self.num_types):
            kept_ratios[i] /= len(self.opponent_offers)
        
        # Higher kept ratio = higher value to opponent
        total_est = sum(kept_ratios[i] * self.counts[i] for i in range(self.num_types))
        if total_est > 0:
            return [kept_ratios[i] * self.total / total_est for i in range(self.num_types)]
        return [self.total / max(1, sum(self.counts))] * self.num_types

    def _generate_offer(self, min_value: int, est_opp: list[float]) -> list[int] | None:
        best_offer = None
        best_score = -1
        
        for alloc in self._all_allocations():
            my_val = self._my_value(alloc)
            if my_val >= min_value:
                opp_share = [c - a for c, a in zip(self.counts, alloc)]
                opp_val = sum(est_opp[i] * opp_share[i] for i in range(self.num_types))
                # Score balances our value with likelihood of acceptance
                score = my_val + opp_val * 0.5
                if score > best_score:
                    best_score = score
                    best_offer = list(alloc)
        return best_offer

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_left = total_turns - self.turn_count + 1
        progress = self.turn_count / total_turns
        is_last_turn = turns_left <= 1
        
        if o is not None:
            self.opponent_offers.append(o)
            my_val = self._my_value(o)
            self.best_offer_value = max(self.best_offer_value, my_val)
            
            # Accept conditions
            if my_val >= self.total * 0.55:
                return None
            if my_val >= self.total * 0.50 and progress >= 0.3:
                return None
            if my_val >= self.total * 0.45 and progress >= 0.6:
                return None
            if my_val >= self.total * 0.40 and progress >= 0.85:
                return None
            if is_last_turn and my_val > 0:
                return None
        
        est_opp = self._estimate_opponent_values()
        
        # Target decreases as negotiation progresses
        target_pct = 0.65 - 0.20 * progress
        target = max(1, int(self.total * target_pct))
        
        offer = self._generate_offer(target, est_opp)
        
        while offer is None and target > 0:
            target -= 1
            offer = self._generate_offer(target, est_opp)
        
        if offer is None:
            offer = [c if v > 0 else 0 for c, v in zip(self.counts, self.values)]
        
        self.my_offers.append(offer)
        return offer