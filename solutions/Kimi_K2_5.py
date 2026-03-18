class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = list(counts)
        self.values = list(values)
        self.n = len(counts)
        self.total_turns = max_rounds * 2
        self.turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Sort item types by my value (ascending) to know what to concede first
        self.concede_order = sorted(range(self.n), key=lambda i: values[i])
        
        # Initial offer: take all items with positive value, give away zero-value items
        self.current_offer = [0] * self.n
        self.current_value = 0
        for i in range(self.n):
            if values[i] > 0:
                self.current_offer[i] = counts[i]
                self.current_value += counts[i] * values[i]
        
        # Pointer for which item type to concede next
        self.concede_idx = 0
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        remaining = self.total_turns - self.turn
        
        # Acceptance strategy: high threshold early, declining to 40% at end
        if o is not None:
            offer_value = sum(a * b for a, b in zip(o, self.values))
            
            # Linear decline from 85% to 40%
            progress = self.turn / self.total_turns
            threshold = self.total_value * (0.85 - 0.45 * progress)
            
            # Last resort: accept anything > 0 on final turn
            if remaining == 0:
                if offer_value > 0:
                    return None
            elif offer_value >= threshold:
                return None
        
        # Offering strategy: be stubborn until last third, then concede lowest-value items
        if remaining < self.total_turns // 3:
            # Time to start conceding - give up one item at a time from lowest value types
            while self.concede_idx < self.n:
                i = self.concede_order[self.concede_idx]
                # Skip items already at zero or with zero value
                if self.values[i] == 0 or self.current_offer[i] == 0:
                    self.concede_idx += 1
                    continue
                
                # Concede one unit of this item type
                self.current_offer[i] -= 1
                self.current_value -= self.values[i]
                break
        
        return list(self.current_offer)