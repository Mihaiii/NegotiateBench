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
    
    def _generate_all_offers(self) -> list[list[int]]:
        offers = []
        def gen(idx, current):
            if idx == self.n:
                offers.append(tuple(current))
                return
            for c in range(self.counts[idx] + 1):
                current.append(c)
                gen(idx + 1, current)
                current.pop()
        gen(0, [])
        return [list(o) for o in offers]
    
    def _estimate_opponent_values(self) -> list[float]:
        """Estimate opponent values from their offers (what they give us = low value to them)."""
        if not self.opponent_offers:
            # Assume inverse of our values initially
            inv = [1.0 / (v + 1) for v in self.values]
            s = sum(inv)
            return [x / s * self.total for x in inv]
        
        # What opponent offers us consistently = low value to them
        # What opponent keeps = high value to them
        weights = [0.0] * self.n
        for offer in self.opponent_offers:
            opp_keeps = self._opponent_gets(offer)
            for i in range(self.n):
                if self.counts[i] > 0:
                    weights[i] += opp_keeps[i]
        
        # Normalize
        total_w = sum(weights) + 0.001
        estimated = [w / total_w * self.total for w in weights]
        
        # Per-item values
        per_item = []
        for i in range(self.n):
            if self.counts[i] > 0:
                per_item.append(estimated[i] / self.counts[i])
            else:
                per_item.append(0)
        return per_item
    
    def _opponent_value(self, my_offer: list[int], opp_vals: list[float]) -> float:
        opp_gets = self._opponent_gets(my_offer)
        return sum(opp_gets[i] * opp_vals[i] for i in range(self.n))
    
    def _find_best_offer(self, min_my_value: int) -> list[int]:
        """Find offer maximizing estimated opponent value while meeting our minimum."""
        all_offers = self._generate_all_offers()
        opp_vals = self._estimate_opponent_values()
        
        candidates = []
        for off in all_offers:
            my_val = self._value(off)
            if my_val >= min_my_value:
                opp_val = self._opponent_value(off, opp_vals)
                candidates.append((off, my_val, opp_val))
        
        if not candidates:
            # Just get max for us
            return max(all_offers, key=lambda x: self._value(x))
        
        # Prioritize opponent value, then our value
        candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)
        return candidates[0][0]
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = 2 * self.max_rounds
        remaining = total_turns - self.turn
        progress = self.turn / total_turns
        
        if o is not None:
            self.opponent_offers.append(o)
            offer_val = self._value(o)
            
            # Final turn - accept if positive
            if remaining == 0:
                return None if offer_val > 0 else [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
            
            # Adaptive acceptance threshold
            base_threshold = 0.5
            # Decrease threshold as we progress
            threshold = self.total * max(0.1, base_threshold - progress * 0.45)
            
            if offer_val >= threshold:
                return None
            
            # Accept good offers late in negotiation
            if progress > 0.7 and offer_val >= self.total * 0.25:
                return None
        
        # Counter-offer strategy
        # Start high, concede gradually
        if progress < 0.2:
            target = self.total * 0.6
        elif progress < 0.4:
            target = self.total * 0.5
        elif progress < 0.6:
            target = self.total * 0.4
        elif progress < 0.8:
            target = self.total * 0.3
        else:
            target = self.total * 0.2
        
        target = max(1, int(target))
        new_offer = self._find_best_offer(target)
        self.my_offers.append(new_offer)
        return new_offer