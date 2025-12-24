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
        
        # Strategic parameters
        self.initial_target = 0.52 * self.total_value  # More conservative start
        self.min_acceptable = 0.35 * self.total_value   # Lower floor
        self.concession_rate = 0.03                      # Slower concession
        
        # Opponent modeling
        self.opponent_offers = []
        self.opponent_estimated_value = None
        self.best_opponent_offer = None
        
        # Item prioritization
        self.item_priority = sorted(range(self.n), 
                                   key=lambda i: values[i], reverse=True)
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        """Main negotiation method - returns None to accept, else counter-offer"""
        self.moves_left -= 1
        
        # Analyze opponent's offer if received
        if o is not None:
            # Track opponent's offer
            self.opponent_offers.append(o)
            
            # Calculate offered value
            offered_value = sum(o[i] * self.values[i] for i in range(self.n))
            
            # Update best opponent offer
            if self.best_opponent_offer is None or offered_value > sum(
                self.best_opponent_offer[i] * self.values[i] for i in range(self.n)
            ):
                self.best_opponent_offer = o
            
            # Estimate opponent's valuation based on their behavior
            self._estimate_opponent_valuation()
            
            # Calculate dynamic target based on progress
            progress = 1 - (self.moves_left / self.total_moves)
            target = self._calculate_target(progress)
            
            # Accept if offer meets or exceeds target
            if offered_value >= target:
                return None
        
        # Make counter-offer
        counter_offer = self._make_counter_offer()
        return counter_offer
    
    def _estimate_opponent_valuation(self):
        """Estimate opponent's valuation from their offers"""
        if len(self.opponent_offers) < 2:
            return
        
        # Look at what opponent keeps vs. gives
        # Assume opponent keeps what they don't offer
        opponent_keeps = []
        for offer in self.opponent_offers:
            keep = [self.counts[i] - offer[i] for i in range(self.n)]
            opponent_keeps.append(keep)
        
        # Estimate based on consistency
        if len(opponent_keeps) >= 2:
            # Take the most common keep pattern as indicator
            # Calculate average keep pattern
            avg_keep = [0] * self.n
            for keep in opponent_keeps:
                for i in range(self.n):
                    avg_keep[i] += keep[i]
            for i in range(self.n):
                avg_keep[i] /= len(opponent_keeps)
            
            # Opponent likely values items they consistently keep
            keep_value = sum(avg_keep[i] * self.values[i] for i in range(self.n))
            if self.opponent_estimated_value is None:
                self.opponent_estimated_value = keep_value
            else:
                # Smooth update
                self.opponent_estimated_value = 0.7 * self.opponent_estimated_value + 0.3 * keep_value
    
    def _calculate_target(self, progress: float) -> float:
        """Calculate our target value based on negotiation progress and opponent behavior"""
        # Base target with linear concession
        target = self.initial_target - (
            (self.initial_target - self.min_acceptable) * progress
        )
        
        # Adjust based on opponent's best offer
        if self.best_opponent_offer is not None:
            best_offer_value = sum(
                self.best_opponent_offer[i] * self.values[i] for i in range(self.n)
            )
            
            # If opponent made a good offer, accept it sooner
            if best_offer_value >= target * 0.95:
                # Lower our target slightly to facilitate agreement
                target = target * 0.95
        
        # Time pressure: sharper concessions near the end
        if progress > 0.75:
            target = target * 0.90
        
        return target
    
    def _make_counter_offer(self) -> list[int]:
        """Construct a strategic counter-offer"""
        progress = 1 - (self.moves_left / self.total_moves)
        target = self._calculate_target(progress)
        
        # Build offer prioritizing high-value items
        offer = [0] * self.n
        remaining = self.counts[:]
        current_value = 0
        
        # First pass: take high-value items to reach target
        for i in self.item_priority:
            if remaining[i] > 0 and current_value < target:
                if self.values[i] > 0:
                    needed = target - current_value
                    take = min(remaining[i], max(1, (needed // self.values[i]) + 1))
                else:
                    take = 0
                take = min(take, remaining[i])
                offer[i] = take
                remaining[i] -= take
                current_value += take * self.values[i]
        
        # Strategic concession: leave room for negotiation
        # Don't be too greedy, especially if time is running out
        if progress > 0.5 and current_value > self.total_value * 0.65:
            # Reduce demand slightly to improve acceptance probability
            excess = current_value - (self.total_value * 0.60)
            if excess > 0:
                # Remove least valuable items
                for i in reversed(self.item_priority):
                    if offer[i] > 0 and self.values[i] > 0:
                        remove = min(offer[i], min(1, int(excess / self.values[i]) + 1))
                        offer[i] -= remove
                        remaining[i] += remove
                        excess -= remove * self.values[i]
                        if excess <= 0:
                            break
        
        # Final check: ensure offer is valid
        total_taken = sum(offer)
        total_available = sum(self.counts)
        if total_taken > total_available:
            # Scale back
            scale = total_available / total_taken
            offer = [int(x * scale) for x in offer]
        
        return offer