class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = list(counts)
        self.values = list(values)
        self.n = len(counts)
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Initialize opponent values with my values (neutral prior)
        self.opp_values = list(values)
        self.last_offer = None
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        remaining = self.total_turns - self.turn
        
        if o is not None:
            my_val = sum(a * b for a, b in zip(o, self.values))
            self._update_beliefs(o)
            
            # Acceptance threshold decreases from 70% to 30% over time
            # Always accept positive value on last possible turn
            threshold = self.total_value * (0.70 - 0.40 * self.turn / self.total_turns)
            if my_val >= threshold or (remaining == 0 and my_val > 0):
                return None
        
        # Generate and store offer
        offer = self._make_offer()
        self.last_offer = offer[:]
        return offer
    
    def _update_beliefs(self, o: list[int]):
        """Update opponent value estimates based on what they offered me."""
        if self.last_offer is None:
            return
            
        for i in range(self.n):
            # What opponent keeps now vs what they would have kept from my last offer
            keep_now = self.counts[i] - o[i]
            keep_before = self.counts[i] - self.last_offer[i]
            
            # If they keep more than I offered them, they value it higher
            if keep_now > keep_before:
                self.opp_values[i] *= 1.25
            elif keep_now < keep_before:
                self.opp_values[i] *= 0.80
                
        # Renormalize to maintain constraint that opponent's total value equals mine
        curr_total = sum(v * c for v, c in zip(self.opp_values, self.counts))
        if curr_total > 0:
            scale = self.total_value / curr_total
            self.opp_values = [max(0.01, v * scale) for v in self.opp_values]
    
    def _make_offer(self) -> list[int]:
        """Generate offer claiming items with highest comparative advantage."""
        # Calculate surplus (my value - estimated opponent value)
        items = [(self.values[i] - self.opp_values[i], self.values[i], i) 
                 for i in range(self.n)]
        
        # Sort by surplus desc, then by my value desc
        items.sort(key=lambda x: (x[0], x[1]), reverse=True)
        
        # Target decreases from 85% to 45% as negotiation progresses
        progress = self.turn / self.total_turns
        target = self.total_value * (0.85 - 0.40 * progress)
        
        offer = [0] * self.n
        current_val = 0
        
        for surplus, my_val, i in items:
            if my_val == 0:
                continue
            
            # Take item if it has positive surplus or if we still need minimum value
            if surplus >= 0 or current_val < target * 0.3:
                offer[i] = self.counts[i]
                current_val += self.counts[i] * my_val
            
            # Stop if we hit target and next items would be inefficient (negative surplus)
            if current_val >= target and surplus >= 0:
                break
        
        return offer