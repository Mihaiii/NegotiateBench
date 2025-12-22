class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.num_types = len(counts)
        self.opponent_offers = []
        self.turn_count = 0
        self.best_offer_received = None
        self.best_offer_value = 0
        
    def _my_value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _all_allocations(self):
        def generate(idx, current):
            if idx == self.num_types:
                yield current.copy()
                return
            for take in range(self.counts[idx] + 1):
                current.append(take)
                yield from generate(idx + 1, current)
                current.pop()
        yield from generate(0, [])
    
    def _estimate_opponent_values(self) -> list[float]:
        if not self.opponent_offers:
            # Assume opponent values what we don't value
            inv = [max(0, self.counts[i] - (self.values[i] * self.counts[i] / max(1, self.total))) 
                   for i in range(self.num_types)]
            total_inv = sum(inv)
            if total_inv > 0:
                return [i * self.total / total_inv for i in inv]
            return [self.total / max(1, sum(self.counts))] * self.num_types
        
        # Items they give us more = lower value to them
        avg_given = [0.0] * self.num_types
        for offer in self.opponent_offers:
            for i in range(self.num_types):
                if self.counts[i] > 0:
                    avg_given[i] += offer[i] / self.counts[i] / len(self.opponent_offers)
        
        est = [(1 - r) for r in avg_given]
        total_est = sum(est[i] * self.counts[i] for i in range(self.num_types))
        if total_est > 0:
            return [e * self.total / total_est for e in est]
        return [self.total / max(1, sum(self.counts))] * self.num_types

    def _generate_offer(self, min_value: int, est_opp: list[float]) -> list[int] | None:
        best_offer = None
        best_opp_value = -1
        
        for alloc in self._all_allocations():
            my_val = self._my_value(alloc)
            if my_val >= min_value:
                opp_share = [c - a for c, a in zip(self.counts, alloc)]
                opp_val = sum(est_opp[i] * opp_share[i] for i in range(self.num_types))
                if opp_val > best_opp_value:
                    best_opp_value = opp_val
                    best_offer = alloc
        return best_offer

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_left = total_turns - self.turn_count + 1
        progress = self.turn_count / total_turns
        
        if o is not None:
            self.opponent_offers.append(o)
            my_val = self._my_value(o)
            
            # Track best offer
            if my_val > self.best_offer_value:
                self.best_offer_value = my_val
                self.best_offer_received = o
            
            # Accept thresholds - be more willing to accept good deals early
            # and any reasonable deal late
            if my_val >= self.total * 0.55:
                return None
            if my_val >= self.total * 0.50 and progress >= 0.2:
                return None
            if my_val >= self.total * 0.45 and progress >= 0.4:
                return None
            if my_val >= self.total * 0.40 and progress >= 0.6:
                return None
            if my_val >= self.total * 0.35 and progress >= 0.8:
                return None
            if my_val > 0 and turns_left <= 2:
                return None
            if my_val >= self.total * 0.25 and turns_left <= 4:
                return None
        
        est_opp = self._estimate_opponent_values()
        
        # Start with reasonable ask, decrease over time
        target_pct = 0.60 - 0.15 * progress
        target = int(self.total * target_pct)
        
        offer = self._generate_offer(target, est_opp)
        
        # Lower requirements if needed
        if offer is None:
            for reduction in range(1, int(self.total) + 1):
                offer = self._generate_offer(target - reduction, est_opp)
                if offer is not None:
                    break
        
        # Fallback
        if offer is None:
            offer = [c if v > 0 else 0 for c, v in zip(self.counts, self.values)]
        
        return offer