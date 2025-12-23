class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.total = sum(counts[i] * values[i] for i in range(len(counts)))
        self.total_rounds = max_rounds
        self.rounds_left = max_rounds
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds_left -= 1
        
        # If partner made an offer, evaluate it
        if o is not None:
            offered_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Accept if offer meets our minimum threshold
            # Use exponential acceptance threshold that increases as time runs out
            acceptance_threshold = 0.30 + 0.20 * (1 - (self.rounds_left / self.total_rounds) ** 2)
            min_acceptable = self.total * acceptance_threshold
            
            if offered_value >= min_acceptable:
                return None
            
            # If we started second and this is the last round, accept almost anything
            if self.me == 1 and self.rounds_left == 0 and offered_value > 0:
                return None
            
            # Build a reasonable counter-offer
            counter = self._build_counter_offer(min_acceptable)
            
            # If no valid counter possible, accept current offer
            if sum(counter[i] * self.values[i] for i in range(len(counter))) < min_acceptable:
                return None
                
            return counter
        
        # First turn: make a reasonable initial demand
        # Start with about 60% of value and be willing to concede
        initial_demand = self._build_counter_offer(self.total * 0.60)
        return initial_demand
    
    def _build_counter_offer(self, target_value: float) -> list[int]:
        """Build a counter-offer targeting a specific value."""
        counter = [0] * len(self.counts)
        remaining_items = self.counts[:]
        
        # Sort items by value (high to low)
        sorted_indices = sorted(range(len(self.counts)), key=lambda i: -self.values[i])
        
        # First pass: take high-value items
        for i in sorted_indices:
            if self.values[i] > 0 and remaining_items[i] > 0:
                # Take as many as possible of high-value items
                items_needed = max(0, int((target_value - sum(counter[j] * self.values[j] for j in range(len(counter))) + self.values[i] - 1) / self.values[i]))
                take = min(remaining_items[i], items_needed + 1)  # +1 buffer
                counter[i] = take
                remaining_items[i] -= take
        
        # Second pass: if target not reached, add more items
        for i in sorted_indices:
            while remaining_items[i] > 0 and sum(counter[j] * self.values[j] for j in range(len(counter))) < target_value:
                counter[i] += 1
                remaining_items[i] -= 1
        
        return counter