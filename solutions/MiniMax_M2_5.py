class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.turn = 0
        
    def _value(self, alloc: list[int]) -> int:
        return sum(a * v for a, v in zip(alloc, self.values))
    
    def _partner_value(self, my_offer: list[int]) -> int:
        """Estimate partner's value for what we're offering them."""
        # Partner gets whatever is not in our offer
        partner_alloc = [c - m for c, m in zip(self.counts, my_offer)]
        # Without knowing their values, assume uniform value distribution
        # This is a heuristic - we'll use a simple assumption
        return sum(partner_alloc)  # Raw count as proxy
    
    def _make_offer(self, target_pct: float) -> list[int]:
        """Create an offer asking for target_pct of total value."""
        target = self.total * target_pct
        offer = [0] * len(self.counts)
        remaining = self.counts.copy()
        
        # Greedily take highest-value items first
        indices = sorted(range(len(self.values)), key=lambda i: -self.values[i])
        
        for idx in indices:
            while remaining[idx] > 0 and self._value(offer) + self.values[idx] <= target:
                offer[idx] += 1
                remaining[idx] -= 1
        
        # If we got nothing, at least get one valuable item
        if self._value(offer) == 0:
            for idx in indices:
                if self.counts[idx] > 0 and self.values[idx] > 0:
                    offer[idx] = min(1, self.counts[idx])
                    break
        
        return offer
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        
        # Calculate progress through negotiation (0 to 1)
        total_turns = self.max_rounds * 2
        progress = self.turn / total_turns
        
        # First turn - make opening offer
        if o is None:
            # Open with 40% target, slightly higher to have room to concede
            return self._make_offer(0.40)
        
        # Received an offer - evaluate it
        offer_value = self._value(o)
        
        # Minimum we accept starts at 35% and decreases to 25% as time runs out
        min_accept_pct = 0.35 - progress * 0.12
        min_accept = self.total * min_accept_pct
        
        # Accept if offer is good enough
        if offer_value >= min_accept:
            return None
        
        # Otherwise make counter-offer
        # Counter-offer targets slightly above what we'd accept + some buffer
        target_pct = min_accept_pct + 0.05 + progress * 0.05
        return self._make_offer(target_pct)