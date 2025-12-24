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
    
    def _generate_offers_by_value(self) -> list[tuple[list[int], int]]:
        """Generate all offers sorted by our value (descending)."""
        offers = []
        def gen(idx, current):
            if idx == self.n:
                off = list(current)
                offers.append((off, self._value(off)))
                return
            for c in range(self.counts[idx] + 1):
                current.append(c)
                gen(idx + 1, current)
                current.pop()
        gen(0, [])
        offers.sort(key=lambda x: -x[1])
        return offers
    
    def _estimate_opponent_value(self, my_offer: list[int]) -> float:
        """Estimate opponent's value based on what they've offered themselves."""
        if not self.opponent_offers:
            return 0
        
        # Infer opponent values from their offers
        opp_keeps_total = [0] * self.n
        for off in self.opponent_offers:
            opp_keeps = self._opponent_gets(off)
            for i in range(self.n):
                opp_keeps_total[i] += opp_keeps[i]
        
        # Normalize to get estimated per-item value weight
        max_keep = max(opp_keeps_total) if opp_keeps_total else 1
        weights = [k / (max_keep + 0.1) for k in opp_keeps_total]
        
        # Estimate what opponent gets from our offer
        opp_gets = self._opponent_gets(my_offer)
        return sum(opp_gets[i] * weights[i] for i in range(self.n))
    
    def _find_best_offer(self, min_value: int, avoid_repeats: bool = True) -> list[int]:
        """Find offer meeting min_value that likely appeals to opponent."""
        all_offers = self._generate_offers_by_value()
        
        candidates = [(off, val, self._estimate_opponent_value(off)) 
                      for off, val in all_offers if val >= min_value]
        
        if not candidates:
            candidates = [(off, val, self._estimate_opponent_value(off)) 
                          for off, val in all_offers if val > 0]
        
        # Sort by estimated opponent value (give them more), then our value
        candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)
        
        if avoid_repeats and self.my_offers:
            for off, _, _ in candidates:
                if off not in self.my_offers:
                    return off
        
        return candidates[0][0] if candidates else self.counts.copy()
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = 2 * self.max_rounds
        progress = self.turn / total_turns
        is_last_turn = self.turn >= total_turns
        is_second_last = self.turn >= total_turns - 1
        
        if o is not None:
            self.opponent_offers.append(o)
            offer_val = self._value(o)
            
            # Accept any positive value on last turn
            if is_last_turn and offer_val > 0:
                return None
            
            # Be more accepting near end
            if is_second_last and offer_val >= self.total * 0.25:
                return None
            
            # Dynamic threshold - start high, decrease over time
            threshold = self.total * max(0.3, 0.6 - progress * 0.5)
            
            if offer_val >= threshold:
                return None
            
            # Accept if offer is improving significantly late game
            if progress > 0.5 and len(self.opponent_offers) > 1:
                best_prev = max(self._value(prev) for prev in self.opponent_offers[:-1])
                if offer_val > best_prev * 1.1 and offer_val >= self.total * 0.25:
                    return None
        
        # Calculate minimum acceptable value for our offer
        min_val = int(self.total * max(0.25, 0.7 - progress * 0.6))
        
        new_offer = self._find_best_offer(min_val, avoid_repeats=True)
        self.my_offers.append(new_offer)
        return new_offer