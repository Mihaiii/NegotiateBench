class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.turn = 0
        self.last_offer = None
        self.opponent_history = []
        
    def _value(self, alloc: list[int]) -> int:
        return sum(a * v for a, v in zip(alloc, self.values))
    
    def _partner_gets(self, my_offer: list[int]) -> list[int]:
        """What the partner receives given our offer."""
        return [c - m for c, m in zip(self.counts, my_offer)]
    
    def _make_offer(self, target_pct: float) -> list[int]:
        """Create an offer targeting a percentage of total value."""
        target = self.total * target_pct
        offer = [0] * len(self.counts)
        remaining = self.counts.copy()
        
        # Sort by value density (value per item)
        indices = sorted(range(len(self.values)), 
                        key=lambda i: (self.values[i], i), reverse=True)
        
        # Greedily add items until we hit target
        for idx in indices:
            while remaining[idx] > 0 and self._value(offer) + self.values[idx] <= target:
                offer[idx] += 1
                remaining[idx] -= 1
        
        # If we got nothing valuable, take highest value item
        if self._value(offer) == 0:
            for idx in indices:
                if self.counts[idx] > 0 and self.values[idx] > 0:
                    offer[idx] = min(1, self.counts[idx])
                    break
        
        return offer
    
    def _estimate_opponent_value(self, their_offer: list[int]) -> int:
        """Estimate opponent's value based on their offer to us."""
        # They get whatever we don't take
        my_share = their_offer if self.me == 1 else [c - o for c, o in zip(self.counts, their_offer)]
        # We know total is equal, so partner value = total - my value
        my_val = self._value(my_share)
        return self.total - my_val
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = self.max_rounds * 2
        
        # Track opponent history
        if o is not None:
            self.opponent_history.append(o)
            self.last_offer = o
        
        # First turn - make opening offer targeting ~45%
        if o is None:
            return self._make_offer(0.45)
        
        # Calculate my value from their offer
        my_value = self._value(o)
        
        # With equal total values, expect ~50%. Accept if >= 40% 
        # But also accept if we're running out of time
        time_left = (total_turns - self.turn) / total_turns
        min_accept = self.total * (0.35 + 0.10 * time_left)
        
        # Also check if opponent is taking a very small share (they might accept)
        opp_value = self.total - my_value
        if opp_value < self.total * 0.20:
            # Opponent is being very generous, accept!
            return None
        
        if my_value >= min_accept:
            return None
        
        # Counter-offer: gradually move toward 50%
        # Target slightly above what we'd accept to leave room for negotiation
        target_pct = min_accept / self.total + 0.05
        target_pct = min(target_pct, 0.50)  # Never target more than 50%
        
        # If we've made the same offer before, try a slightly different mix
        new_offer = self._make_offer(target_pct)
        
        # Sometimes make a more aggressive offer if opponent seems desperate
        if len(self.opponent_history) >= 2:
            # Check if opponent's last offers were small for them
            recent_opp = self._partner_gets(self.last_offer)
            opp_last_val = sum(r * v for r, v in zip(recent_opp, self.values))
            if opp_last_val < self.total * 0.3:
                # They're accepting little, so we can push harder
                target_pct = min(target_pct + 0.05, 0.50)
                new_offer = self._make_offer(target_pct)
        
        return new_offer