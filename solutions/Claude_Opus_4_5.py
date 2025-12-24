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
        self.all_offers = self._generate_all_offers()
        self.offer_values = {tuple(o): self._value(o) for o in self.all_offers}
        
    def _value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _opponent_gets(self, my_offer: list[int]) -> list[int]:
        return [self.counts[i] - my_offer[i] for i in range(self.n)]
    
    def _generate_all_offers(self) -> list[list[int]]:
        offers = []
        def gen(idx, current):
            if idx == self.n:
                offers.append(list(current))
                return
            for c in range(self.counts[idx] + 1):
                current.append(c)
                gen(idx + 1, current)
                current.pop()
        gen(0, [])
        return offers
    
    def _infer_opponent_preferences(self) -> list[float]:
        """Infer per-item opponent values based on their offer patterns."""
        if not self.opponent_offers:
            # Start with uniform assumption
            return [self.total / sum(self.counts)] * self.n if sum(self.counts) > 0 else [0] * self.n
        
        # Analyze what opponent keeps vs gives
        keep_scores = [0.0] * self.n
        give_scores = [0.0] * self.n
        
        for idx, offer in enumerate(self.opponent_offers):
            weight = idx + 1  # Later offers weighted more
            opp_keeps = self._opponent_gets(offer)
            for i in range(self.n):
                if self.counts[i] > 0:
                    keep_ratio = opp_keeps[i] / self.counts[i]
                    keep_scores[i] += keep_ratio * weight
                    give_scores[i] += (1 - keep_ratio) * weight
        
        # Items they keep more = higher value to them
        per_item = []
        for i in range(self.n):
            if self.counts[i] > 0 and (keep_scores[i] + give_scores[i]) > 0:
                ratio = keep_scores[i] / (keep_scores[i] + give_scores[i] + 0.01)
                per_item.append(ratio * 2)  # Scale factor
            else:
                per_item.append(0.5)
        
        # Normalize to total
        total_est = sum(per_item[i] * self.counts[i] for i in range(self.n))
        if total_est > 0:
            per_item = [p * self.total / total_est for p in per_item]
        
        return per_item
    
    def _estimate_opponent_value(self, my_offer: list[int], opp_vals: list[float]) -> float:
        opp_gets = self._opponent_gets(my_offer)
        return sum(opp_gets[i] * opp_vals[i] for i in range(self.n))
    
    def _find_pareto_offers(self, min_value: int) -> list[tuple[list[int], int, float]]:
        """Find offers meeting our minimum that maximize opponent's estimated value."""
        opp_vals = self._infer_opponent_preferences()
        
        candidates = []
        for off in self.all_offers:
            my_val = self.offer_values[tuple(off)]
            if my_val >= min_value:
                opp_val = self._estimate_opponent_value(off, opp_vals)
                candidates.append((off, my_val, opp_val))
        
        # Sort by opponent value (descending), then by our value (descending)
        candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)
        return candidates
    
    def _select_offer(self, progress: float) -> list[int]:
        """Select strategic offer based on negotiation progress."""
        # Dynamic minimum based on progress
        if progress < 0.25:
            min_val = int(self.total * 0.55)
        elif progress < 0.5:
            min_val = int(self.total * 0.45)
        elif progress < 0.75:
            min_val = int(self.total * 0.35)
        else:
            min_val = max(1, int(self.total * 0.2))
        
        candidates = self._find_pareto_offers(min_val)
        
        if not candidates:
            # Fallback: lower our minimum
            candidates = self._find_pareto_offers(1)
        
        if not candidates:
            return self.counts.copy()
        
        # Pick top candidate (best for opponent while meeting our threshold)
        # Avoid repeating exact same offer
        for cand in candidates:
            if cand[0] not in self.my_offers or len(candidates) == 1:
                return cand[0]
        
        return candidates[0][0]
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = 2 * self.max_rounds
        remaining = total_turns - self.turn
        progress = self.turn / total_turns
        
        if o is not None:
            self.opponent_offers.append(o)
            offer_val = self._value(o)
            
            # Last turn - accept anything positive
            if remaining == 0:
                return None if offer_val > 0 else self._select_offer(1.0)
            
            # Second to last (our last chance to offer) - be more accepting
            if remaining == 1 and offer_val >= self.total * 0.15:
                return None
            
            # Dynamic acceptance threshold
            if progress < 0.3:
                threshold = self.total * 0.5
            elif progress < 0.6:
                threshold = self.total * 0.4
            elif progress < 0.8:
                threshold = self.total * 0.3
            else:
                threshold = self.total * 0.2
            
            # Accept if meets threshold
            if offer_val >= threshold:
                return None
            
            # Accept improving offers in late game
            if progress > 0.6 and self.opponent_offers:
                prev_best = max(self._value(prev) for prev in self.opponent_offers[:-1]) if len(self.opponent_offers) > 1 else 0
                if offer_val > prev_best and offer_val >= self.total * 0.2:
                    return None
        
        # Make counter-offer
        new_offer = self._select_offer(progress)
        self.my_offers.append(new_offer)
        return new_offer