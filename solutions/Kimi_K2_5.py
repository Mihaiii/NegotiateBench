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
        
        # Initialize opponent values with my values as neutral prior
        self.opp_values = list(values)
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        remaining = self.total_turns - self.turn
        
        # Process opponent offer
        if o is not None:
            my_val = sum(a * b for a, b in zip(o, self.values))
            self._update_beliefs(o)
            
            # Acceptance strategy with declining threshold
            if remaining == 0:
                # Last chance: accept any positive offer
                if my_val > 0:
                    return None
            else:
                # Threshold decreases from 60% to 35% over time
                progress = self.turn / self.total_turns
                threshold = self.total_value * (0.60 - 0.25 * progress)
                if my_val >= threshold:
                    return None
        
        # Generate counter-offer
        return self._make_offer(remaining)
    
    def _update_beliefs(self, o: list[int]):
        """Update opponent value estimates based on what they offered."""
        for i in range(self.n):
            they_keep = self.counts[i] - o[i]
            
            if they_keep == self.counts[i]:
                # They keep all: likely high value to them
                self.opp_values[i] *= 1.2
            elif o[i] == self.counts[i]:
                # They give all to me: likely low value to them
                self.opp_values[i] *= 0.8
        
        # Renormalize to maintain total value constraint
        curr_total = sum(v * c for v, c in zip(self.opp_values, self.counts))
        if curr_total > 0:
            scale = self.total_value / curr_total
            self.opp_values = [max(0.01, v * scale) for v in self.opp_values]
    
    def _make_offer(self, remaining: int) -> list[int]:
        """Generate offer based on comparative advantage."""
        # Calculate comparative advantage ratio for each item
        items = []
        for i in range(self.n):
            my_v = self.values[i]
            opp_v = self.opp_values[i]
            if opp_v < 0.01:
                ratio = float('inf') if my_v > 0 else 0
            else:
                ratio = my_v / opp_v if my_v > 0 else 0
            items.append((ratio, my_v, i))
        
        # Sort by ratio descending (items I should keep first)
        items.sort(key=lambda x: (x[0], x[1]), reverse=True)
        
        # Target decreases from 70% to 40% as deadline approaches
        if remaining == 0:
            target = self.total_value * 0.40
        else:
            progress = self.turn / self.total_turns
            target = self.total_value * (0.70 - 0.30 * progress)
        
        offer = [0] * self.n
        current_val = 0
        
        # Claim high-ratio items until target reached
        for ratio, my_v, i in items:
            if my_v == 0:
                continue
            if current_val >= target:
                break
            
            offer[i] = self.counts[i]
            current_val += self.counts[i] * my_v
        
        # Ensure opponent gets at least 25% estimated value to encourage acceptance
        opp_val = sum((self.counts[i] - offer[i]) * self.opp_values[i] for i in range(self.n))
        min_opp = self.total_value * 0.25
        
        if opp_val < min_opp and remaining > 0:
            # Concede least valuable items
            for ratio, my_v, i in reversed(items):
                if offer[i] > 0:
                    offer[i] = 0
                    opp_val += self.counts[i] * self.opp_values[i]
                    if opp_val >= min_opp:
                        break
        
        return offer