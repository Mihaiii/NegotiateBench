class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me  # 0 if I go first, 1 if second
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.turn = 0
        self.total = sum(c * v for c, v in zip(counts, values))
        # Sort item indices by my value (highest first)
        self.items = sorted(range(len(counts)), key=lambda i: -values[i])
    
    def value(self, offer):
        """Calculate the value of an offer to me."""
        return sum(self.values[i] * offer[i] for i in range(len(offer)))
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = self.max_rounds * 2
        remaining_turns = total_turns - self.turn + 1
        
        # Evaluate partner's offer
        if o is not None:
            offer_value = self.value(o)
            
            # Last turn: accept any offer (better than no agreement)
            if remaining_turns == 1:
                return None
            
            # Calculate acceptance threshold (decreases as turns progress)
            threshold = 0.6 - 0.3 * (self.turn - 1) / total_turns
            if self.me == 1:
                threshold -= 0.05  # Second mover accepts less
            
            # Accept if offer meets threshold
            if offer_value >= self.total * max(threshold, 0.3):
                return None
        
        # Make counter-offer
        # Target fraction decreases as turns progress
        target_fraction = 0.7 - 0.2 * (self.turn - 1) / total_turns
        if self.me == 1:
            target_fraction -= 0.05
        
        target_value = self.total * target_fraction
        
        # Greedy: take highest value items first
        offer = [0] * len(self.counts)
        current_value = 0
        
        for i in self.items:
            if self.values[i] == 0 or current_value >= target_value:
                continue
            
            # Calculate how many of this item to take
            remaining = target_value - current_value
            take = min(self.counts[i], (remaining + self.values[i] - 1) // self.values[i])
            offer[i] = take
            current_value += self.values[i] * take
        
        return offer