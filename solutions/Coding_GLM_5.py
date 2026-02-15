class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.round = 0
        self.total = sum(c * v for c, v in zip(counts, values))
        self.partner_keeps = [0] * len(counts)

    def offer_value(self, offer):
        return sum(v * o for v, o in zip(self.values, offer))

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.round += 1
        remaining = self.max_rounds - self.round
        
        if o is not None:
            # Learn from partner's offer
            for i, (c, offered) in enumerate(zip(self.counts, o)):
                self.partner_keeps[i] = max(self.partner_keeps[i], c - offered)
            
            # Evaluate offer
            value = self.offer_value(o)
            
            # Accept if it's good enough
            if remaining <= 0:
                return None  # Accept anything on last turn to ensure a deal
            
            threshold = self.total * (0.5 - 0.1 * min(self.round - 1, 3))
            threshold = max(threshold, self.total * 0.2)
            
            if value >= threshold:
                return None  # Accept
        
        # Make counter-offer
        offer = self.counts.copy()
        
        for i, (c, v) in enumerate(zip(self.counts, self.values)):
            if v == 0:
                offer[i] = 0  # Give away items we don't value
            elif remaining <= 1:
                offer[i] = max(c - self.partner_keeps[i], c // 2)  # Be generous on last chance
            elif self.partner_keeps[i] > 0:
                offer[i] = c - min(self.partner_keeps[i], c - 1)  # Give partner some of what they want
            else:
                offer[i] = c  # Keep all for now
        
        return offer