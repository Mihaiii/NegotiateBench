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
        
        # Sort items by our value (ascending) - concede low-value items first
        self.concede_order = sorted(range(self.n), key=lambda i: self.values[i])
        
        # Current offer: start by claiming all items with positive value
        self.current_offer = [c if v > 0 else 0 for c, v in zip(counts, values)]
        
        # Track opponent's last offer to detect concessions
        self.prev_offer = None
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        remaining = self.total_turns - self.turn
        
        # Acceptance strategy
        if o is not None:
            offer_value = sum(a * b for a, b in zip(o, self.values))
            
            # Threshold decreases linearly from 75% to 30% of total value
            progress = self.turn / self.total_turns if self.total_turns > 0 else 1
            threshold = self.total_value * (0.75 - 0.45 * progress)
            
            # On final turn, accept anything > 0 to avoid no-deal
            if remaining == 0:
                if offer_value > 0:
                    return None
            elif offer_value >= threshold:
                return None
            
            # Detect opponent concessions (are they giving us more?)
            if self.prev_offer is not None:
                prev_val = sum(a * b for a, b in zip(self.prev_offer, self.values))
                if offer_value > prev_val:
                    # Opponent is conceding, we should also concede slightly faster
                    pass
            self.prev_offer = o[:]
        
        # Offering strategy: concede gradually over time
        # Start conceding immediately but slowly, accelerate in final rounds
        if remaining > 0:
            # Calculate how "generous" we should be based on time elapsed
            # Early: keep ~90%, Late: keep ~40%
            target_keep_ratio = 0.90 - 0.50 * (self.turn / self.total_turns)
            target_value = self.total_value * target_keep_ratio
            
            current_value = sum(self.current_offer[i] * self.values[i] for i in range(self.n))
            
            # If we're above target, concede something
            if current_value > target_value:
                # Concede the lowest-value item we still have
                for idx in self.concede_order:
                    if self.current_offer[idx] > 0:
                        self.current_offer[idx] -= 1
                        break
            
            # Also consider conceding worthless items immediately
            for i in range(self.n):
                if self.values[i] == 0 and self.current_offer[i] > 0:
                    self.current_offer[i] = 0
        
        # Ensure we never return more than we have
        for i in range(self.n):
            if self.current_offer[i] > self.counts[i]:
                self.current_offer[i] = self.counts[i]
            if self.current_offer[i] < 0:
                self.current_offer[i] = 0
                
        return self.current_offer[:]