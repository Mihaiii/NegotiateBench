class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.me = me  # 0 = first, 1 = second
        self.turn = 0
        self.total = sum(c * v for c, v in zip(counts, values))
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        round_num = (self.turn + 1) // 2
        
        # Check if we should accept opponent's offer
        if o is not None:
            my_value = sum(o[i] * self.values[i] for i in range(len(o)))
            # Calculate acceptable threshold - more demanding in early rounds, less in late rounds
            # Use a minimum floor to ensure we don't accept too little
            min_acceptable = self.total * max(0.2, 0.5 - (round_num / (self.max_rounds * 2)))
            
            if my_value >= min_acceptable:
                return None  # Accept the offer
        
        # If we get here, we need to make a counter-offer
        # Target a value that decreases as rounds progress (concession strategy)
        target_value = int(self.total * max(0.25, 0.6 - (round_num / (self.max_rounds * 1.5))))
        
        # Greedy approach: take items with highest value-to-count ratio first
        # Value per item for each type
        vpi = [(self.values[i], i) for i in range(len(self.counts))]
        vpi.sort(reverse=True)
        
        offer = [0] * len(self.counts)
        remaining = self.counts.copy()
        
        # First pass: try to maximize value per item
        for val, i in vpi:
            if remaining[i] > 0 and val > 0:
                take = min(remaining[i], max(1, remaining[i] // 2))
                offer[i] = take
                remaining[i] -= take
        
        # Calculate current value
        current_value = sum(offer[i] * self.values[i] for i in range(len(offer)))
        
        # If not enough, adjust by taking more of valuable items
        if current_value < target_value:
            # Try to add more items starting from most valuable
            for val, i in vpi:
                if remaining[i] > 0:
                    while remaining[i] > 0 and current_value < target_value:
                        offer[i] += 1
                        remaining[i] -= 1
                        current_value += val
                        if val == 0:
                            break
        
        return offer