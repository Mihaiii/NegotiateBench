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
        
    def _value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _infer_opponent_values(self) -> list[float]:
        """Estimate opponent's relative preferences from their offers."""
        if not self.opponent_offers:
            return [1.0] * self.n
        
        # Items opponent keeps for themselves (counts - what they offer us)
        kept_counts = [0.0] * self.n
        for offer in self.opponent_offers:
            for i in range(self.n):
                kept_counts[i] += self.counts[i] - offer[i]
        
        # Normalize - higher = opponent values more
        total_kept = sum(kept_counts) + 0.01
        return [k / total_kept for k in kept_counts]
    
    def _generate_all_splits(self):
        """Generate all possible splits."""
        splits = []
        def gen(idx, current):
            if idx == self.n:
                splits.append(current.copy())
                return
            for c in range(self.counts[idx] + 1):
                current.append(c)
                gen(idx + 1, current)
                current.pop()
        gen(0, [])
        return splits
    
    def _best_offer(self, min_my_value: int, opponent_prefs: list[float]) -> list[int] | None:
        """Find best offer giving us at least min_my_value, maximizing opponent's likely value."""
        splits = self._generate_all_splits()
        best = None
        best_score = -1
        
        for split in splits:
            my_val = self._value(split)
            if my_val < min_my_value:
                continue
            
            # Score by what we give opponent (weighted by their inferred preferences)
            opp_score = sum((self.counts[i] - split[i]) * opponent_prefs[i] for i in range(self.n))
            # Tie-break: prefer giving away our zero-value items
            zero_given = sum(self.counts[i] - split[i] for i in range(self.n) if self.values[i] == 0)
            
            score = (opp_score, zero_given, -my_val)  # Give more, take less
            if best is None or score > best_score:
                best_score = score
                best = split
        
        return best
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = 2 * self.max_rounds
        progress = self.turn / total_turns
        is_final = self.turn >= total_turns
        
        if o is not None:
            self.opponent_offers.append(o)
            offer_val = self._value(o)
            
            # Accept conditions
            if is_final:
                return None if offer_val > 0 else self._best_offer(1, self._infer_opponent_values())
            
            # Dynamic threshold: starts at 55%, drops to 25%
            threshold = self.total * max(0.25, 0.55 - 0.35 * progress)
            if offer_val >= threshold:
                return None
        
        # Demand curve: starts at 75%, drops to 30%
        demand = self.total * max(0.30, 0.75 - 0.50 * progress)
        target = max(1, int(demand))
        
        opp_prefs = self._infer_opponent_values()
        result = self._best_offer(target, opp_prefs)
        
        if result is None:
            result = self._best_offer(1, opp_prefs)
        
        return result