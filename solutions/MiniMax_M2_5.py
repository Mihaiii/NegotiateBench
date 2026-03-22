class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.me = me
        self.turn = 0
        self.total = sum(c * v for c, v in zip(counts, values))
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        round_num = (self.turn + 1) // 2
        remaining_rounds = self.max_rounds - round_num + 1
        
        # If this is our first turn and we go second, opponent made first offer
        # Analyze their offer to estimate their values
        if o is not None:
            my_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Calculate opponent's share - they get the remainder
            opponent_value = self.total - my_value
            
            # Calculate minimum acceptable - be more demanding
            # As rounds decrease, acceptance threshold increases
            min_acceptable = self.total * (0.35 + 0.1 * (self.max_rounds - remaining_rounds) / max(1, self.max_rounds - 1))
            
            # In last rounds, accept any reasonable offer
            if remaining_rounds <= 2 and my_value >= self.total * 0.4:
                return None
            
            if my_value >= min_acceptable:
                return None
        
        # Make a counter-offer
        # If we go first, start demanding more (high target)
        # If we go second, start from opponent's demand and improve slightly
        
        # Target more as we progress - be aggressive
        target_pct = max(0.45, 0.55 - (round_num - 1) * 0.15 / max(1, self.max_rounds))
        target_value = int(self.total * target_pct)
        
        # Build offer prioritizing items we value most
        # We want items with high value-per-item ratio
        vpi = [(self.values[i] / max(1, self.counts[i]), i) for i in range(len(self.counts))]
        vpi.sort(reverse=True)  # Highest value first
        
        offer = [0] * len(self.counts)
        remaining = self.counts.copy()
        
        # First, take items we value most (up to target value)
        for ratio, i in vpi:
            if remaining[i] > 0:
                # Take as many as possible while maintaining fairness perception
                max_take = remaining[i]
                # Don't take everything of high-value items (leave some for opponent)
                if self.values[i] > 0:
                    max_take = min(remaining[i], max(1, self.counts[i] // 2 + 1))
                
                offer[i] = max_take
                remaining[i] -= max_take
        
        # Calculate current value
        current_value = sum(offer[i] * self.values[i] for i in range(len(offer)))
        
        # If we need more value, take additional items
        if current_value < target_value:
            for ratio, i in vpi:
                if remaining[i] > 0 and current_value < target_value:
                    take = min(remaining[i], target_value - current_value + self.values[i] - 1) // self.values[i] if self.values[i] > 0 else remaining[i]
                    take = max(0, take)
                    offer[i] += take
                    current_value += take * self.values[i]
                    remaining[i] -= take
        
        # Ensure we offer a valid split (all objects allocated)
        allocated = sum(offer)
        total_objects = sum(self.counts)
        
        if allocated < total_objects:
            # Give opponent remaining items
            for i in range(len(remaining)):
                if remaining[i] > 0:
                    offer[i] += remaining[i]
                    remaining[i] = 0
        
        return offer