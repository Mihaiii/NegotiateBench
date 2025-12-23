class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.total = sum(counts[i] * values[i] for i in range(len(counts)))
        self.total_rounds = max_rounds
        self.rounds_left = max_rounds
        self.sorted_indices = sorted(range(len(counts)), key=lambda i: -values[i])
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds_left -= 1
        
        # If partner made an offer, evaluate it
        if o is not None:
            offered_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Adaptive acceptance threshold
            progress = 1 - (self.rounds_left / self.total_rounds)
            acceptance_threshold = 0.50 - (progress * 0.20)  # 50% -> 30%
            min_acceptable = self.total * acceptance_threshold
            
            # Accept if offer meets minimum threshold
            if offered_value >= min_acceptable:
                return None
            
            # Last round: accept if offer has any value
            if self.rounds_left == 0:
                return None
            
            # Build counter-offer
            target = self.total * (acceptance_threshold + 0.10)  # Target 60% -> 40%
            counter = self._build_counter_offer(target)
            
            # If counter doesn't meet minimum, accept current offer
            counter_value = sum(counter[i] * self.values[i] for i in range(len(counter)))
            if counter_value < min_acceptable:
                return None
                
            return counter
        
        # First turn: make initial demand
        target = self.total * 0.60  # Aim for 60%
        return self._build_counter_offer(target)
    
    def _build_counter_offer(self, target_value: float) -> list[int]:
        """Build counter-offer targeting specific value, prioritizing high-value items."""
        counter = [0] * len(self.counts)
        remaining = self.counts[:]
        
        # First pass: take high-value items to meet target
        for i in self.sorted_indices:
            if remaining[i] > 0:
                value_per_item = self.values[i]
                if value_per_item > 0:
                    needed = max(0, int((target_value - sum(counter[j] * self.values[j] for j in range(len(counter))) + value_per_item - 1) / value_per_item))
                    take = min(remaining[i], needed)
                    if take > 0:
                        counter[i] = take
                        remaining[i] -= take
        
        # Second pass: fill with more items if needed
        for i in self.sorted_indices:
            if remaining[i] > 0 and sum(counter[j] * self.values[j] for j in range(len(counter))) < target_value:
                counter[i] += 1
                remaining[i] -= 1
        
        return counter