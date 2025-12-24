class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds
        
        # Total value calculation
        self.total_value = sum(counts[i] * values[i] for i in range(self.n))
        
        # Round tracking
        self.total_moves = max_rounds * 2
        self.moves_left = self.total_moves
        self.is_first = (me == 0)
        
        # Strategic parameters (optimized based on negotiation patterns)
        self.initial_target = 0.58 * self.total_value  # Start at 58%
        self.min_acceptable = 0.38 * self.total_value   # Minimum 38%
        self.concession_rate = 0.04                      # Concede 4% per round
        
        # Item prioritization
        self.item_priority = sorted(range(self.n), 
                                   key=lambda i: values[i], reverse=True)
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        """Main negotiation method - returns None to accept, else counter-offer"""
        self.moves_left -= 1
        
        # Calculate negotiation progress
        progress = 1 - (self.moves_left / self.total_moves)
        
        # Analyze opponent's offer if received
        if o is not None:
            offered_value = sum(o[i] * self.values[i] for i in range(self.n))
            
            # Calculate dynamic target based on progress
            target = self._calculate_target(progress)
            
            # Accept if offer meets or exceeds target
            if offered_value >= target:
                return None
        
        # Make counter-offer
        counter_offer = self._make_counter_offer(progress)
        return counter_offer
    
    def _calculate_target(self, progress: float) -> float:
        """Calculate our target value based on negotiation progress"""
        # Linear concession from initial target to min acceptable
        target = self.initial_target - (
            (self.initial_target - self.min_acceptable) * progress
        )
        return target
    
    def _make_counter_offer(self, progress: float) -> list[int]:
        """Construct a strategic counter-offer"""
        target = self._calculate_target(progress)
        
        # Build offer prioritizing high-value items
        offer = [0] * self.n
        remaining = self.counts[:]
        current_value = 0
        
        # First pass: take high-value items until we reach target
        for i in self.item_priority:
            if remaining[i] > 0 and current_value < target:
                # Take enough to reach target
                if self.values[i] > 0:
                    needed = target - current_value
                    take = min(remaining[i], (needed // self.values[i]) + 1)
                else:
                    take = 0
                take = min(take, remaining[i])
                offer[i] = take
                remaining[i] -= take
                current_value += take * self.values[i]
        
        # Second pass: add more items if needed
        if current_value < target:
            for i in self.item_priority:
                if remaining[i] > 0 and self.values[i] > 0:
                    take = min(remaining[i], 1)
                    offer[i] += take
                    remaining[i] -= take
                    current_value += take * self.values[i]
                    if current_value >= target:
                        break
        
        # Strategic adjustment: if asking for >80%, reduce slightly
        if current_value > self.total_value * 0.80:
            # Remove least valuable items to improve acceptability
            for i in reversed(self.item_priority):
                if offer[i] > 0:
                    offer[i] -= 1
                    remaining[i] += 1
                    break
        
        return offer