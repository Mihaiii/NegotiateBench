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
        
        # Strategic thresholds
        self.target = self.total_value * 0.48  # Start at 48%
        self.minimum = self.total_value * 0.38  # Accept as low as 38%
        self.optimal = self.total_value * 0.45  # Optimal target
        
        # Track opponent's best offer to us
        self.best_offer_value = 0
        self.best_offer = None
        self.offer_count = 0
        self.opponent_concession_rate = 0
        
        # Item prioritization - value efficiency
        self.item_priority = sorted(range(self.n), 
                                   key=lambda i: values[i], reverse=True)
        
        # Strategic parameters
        self.aggressive_threshold = self.total_value * 0.42
        
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
            # Calculate opponent's concession rate
            if self.offer_count > 1:
                self.opponent_concession_rate = (self.best_offer_value - offered_value) / self.offer_count
        
        # Calculate time pressure
        time_pressure = 1 - (self.moves_left / self.total_moves)
        
        # Calculate current acceptable threshold
        acceptable = self._calculate_acceptable_threshold(time_pressure)
        
        # CRITICAL: Accept if offer meets our current threshold
        if offered_value >= acceptable:
            return None
        
        # Make counter-offer with strategic target
        next_target = self._calculate_next_target(time_pressure, offered_value)
        return self._build_offer(next_target)
    
    def _calculate_acceptable_threshold(self, time_pressure: float) -> float:
        """Calculate minimum value we'll accept based on time pressure"""
        # More aggressive acceptance as deadline approaches
        # Start at 48%, drop to 38% by the end
        reduction = time_pressure * (self.target - self.minimum)
        return max(self.minimum, self.target - reduction)
    
    def _calculate_next_target(self, time_pressure: float, last_offer: float) -> float:
        """Calculate our next offer target with strategic concessions"""
        # If opponent made a reasonable offer, move towards it
        if self.best_offer_value > self.optimal * 0.85:
            # Concede towards opponent's best offer more aggressively
            blend_factor = 0.6  # 60% towards opponent, 40% towards our target
            return blend_factor * self.best_offer_value + (1 - blend_factor) * self.target
        
        # Otherwise, concede based on time pressure
        # More aggressive concessions in later rounds
        concession_rate = 0.3 + (time_pressure * 0.4)  # 30% to 70% of potential concession
        potential_concession = (self.target - self.minimum) * concession_rate
        return max(self.minimum, self.target - potential_concession)
    
    def _build_offer(self, target_value: float) -> list[int]:
        """Build an offer that meets target value efficiently"""
        offer = [0] * self.n
        remaining = self.counts[:]
        current_value = 0
        
        # Prioritize items by value per unit
        for i in self.item_priority:
            if remaining[i] > 0 and current_value < target_value:
                item_value = self.values[i]
                if item_value > 0:
                    # Take enough to reach target efficiently
                    needed = target_value - current_value
                    take = min(remaining[i], max(1, int(needed / item_value)))
                else:
                    take = 0
                
                take = min(take, remaining[i])
                offer[i] = take
                remaining[i] -= take
                current_value += take * item_value
        
        # If we haven't reached target, take remaining items
        if current_value < target_value:
            for i in range(self.n):
                if remaining[i] > 0:
                    offer[i] = remaining[i]
                    remaining[i] = 0
        
        return offer