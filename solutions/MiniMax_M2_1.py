class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_rounds = max_rounds
        self.total_moves = max_rounds * 2
        self.moves_left = self.total_moves
        self.is_first = (me == 0)
        
        # Total value calculation
        self.total_value = sum(counts[i] * values[i] for i in range(self.n))
        
        # Key strategy: Prioritize agreement over maximization
        # Start more aggressively but be willing to concede
        self.target = self.total_value * 0.55  # Start at 55%
        self.minimum = self.total_value * 0.40  # Absolute minimum 40%
        
        # Track opponent's best offer to us
        self.best_offer_value = 0
        self.best_offer = None
        self.offer_count = 0
        
        # Item prioritization - value efficiency
        self.item_priority = sorted(range(self.n), 
                                   key=lambda i: values[i] / max(1, counts[i]), reverse=True)
        
        # Simple opponent adaptation
        self.opponent_stubbornness = 0.5  # Will adjust based on behavior
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        """Main negotiation method - returns None to accept, else counter-offer"""
        self.moves_left -= 1
        self.offer_count += 1
        
        # First move - make initial offer
        if o is None:
            return self._build_offer(self.target)
        
        # Calculate value of opponent's offer
        offered_value = sum(o[i] * self.values[i] for i in range(self.n))
        
        # Update best offer tracking
        if offered_value > self.best_offer_value:
            self.best_offer_value = offered_value
            self.best_offer = o
        
        # Calculate current acceptable threshold
        # More aggressive as time runs out, but still reasonable
        time_pressure = 1 - (self.moves_left / self.total_moves)
        acceptable = self._calculate_acceptable_threshold(time_pressure)
        
        # Accept if offer meets our current threshold
        if offered_value >= acceptable:
            return None
        
        # Opponent rejected our last offer - adapt strategy
        if self.offer_count > 1:
            # If opponent keeps rejecting good offers, they're stubborn
            if offered_value > self.target * 0.8:
                self.opponent_stubbornness = min(1.0, self.opponent_stubbornness + 0.1)
        
        # Make counter-offer
        return self._build_offer(self._calculate_next_target(time_pressure))
    
    def _calculate_acceptable_threshold(self, time_pressure: float) -> float:
        """Calculate minimum value we'll accept based on time pressure"""
        # Base threshold starts high and decreases with time
        base_threshold = self.target * (1 - time_pressure * 0.3)  # Only 30% reduction over time
        return max(self.minimum, base_threshold)
    
    def _calculate_next_target(self, time_pressure: float) -> float:
        """Calculate our next offer target"""
        # If opponent made a reasonable offer, move towards it
        if self.best_offer_value > self.target * 0.8:
            # Meet in the middle with opponent's best offer
            return (self.target + self.best_offer_value) / 2
        
        # Otherwise, concede based on time but not too much
        concession = time_pressure * (self.target - self.minimum) * 0.5  # Only 50% of potential concession
        return max(self.minimum, self.target - concession)
    
    def _build_offer(self, target_value: float) -> list[int]:
        """Build an offer that meets target value efficiently"""
        offer = [0] * self.n
        remaining = self.counts[:]
        current_value = 0
        
        # Prioritize items that give best value per unit
        for i in self.item_priority:
            if remaining[i] > 0 and current_value < target_value:
                item_value = self.values[i]
                if item_value > 0:
                    # Take enough to reach target efficiently
                    needed = target_value - current_value
                    take = min(remaining[i], max(1, int(needed / item_value) + 1))
                else:
                    take = 0
                
                take = min(take, remaining[i])
                offer[i] = take
                remaining[i] -= take
                current_value += take * item_value
        
        # If we haven't reached target, take remaining items (including zero-value ones)
        if current_value < target_value:
            for i in range(self.n):
                if remaining[i] > 0:
                    offer[i] = remaining[i]
                    remaining[i] = 0
        
        return offer