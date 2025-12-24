class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.rounds = max_rounds
        
        # Total value calculation
        self.total_value = sum(counts[i] * values[i] for i in range(self.n))
        self.total_moves = max_rounds * 2
        self.moves_left = self.total_moves
        
        # Track negotiation progress
        self.is_first = (me == 0)
        self.round_number = 1
        self.offer_count = 0
        
        # Track opponent behavior
        self.opponent_offers = []
        self.opponent_responses = []  # True if accepted, False if rejected
        self.best_offer_received = None
        self.best_offer_value = -1
        
        # Strategic parameters
        self.initial_demand_ratio = 0.65  # Start by demanding 65% of value
        self.min_acceptable_ratio = 0.48   # Minimum we'll accept
        self.concession_rate = 0.05        # How much to concede per round
        
        # Item prioritization
        self.item_values = list(zip(range(self.n), values, counts))
        self.sorted_indices = sorted(range(self.n), key=lambda i: values[i], reverse=True)
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        """Main negotiation method - returns None to accept, else counter-offer"""
        self.moves_left -= 1
        progress = 1 - (self.moves_left / self.total_moves)
        
        # Analyze opponent's offer if received
        if o is not None:
            offered_value = sum(o[i] * self.values[i] for i in range(self.n))
            
            # Track opponent behavior
            self.opponent_offers.append((o[:], offered_value))
            if offered_value > self.best_offer_value:
                self.best_offer_value = offered_value
                self.best_offer_received = o[:]
            
            # Calculate dynamic acceptance threshold
            accept_threshold = self._calculate_acceptance_threshold(progress, offered_value)
            
            # Accept if offer meets or exceeds threshold
            if offered_value >= accept_threshold:
                return None
            
            # On last move, be more willing to accept
            if self.moves_left <= 1:
                if offered_value >= self.total_value * self.min_acceptable_ratio:
                    return None
        
        # Make a counter-offer
        counter_offer = self._make_counter_offer(progress)
        self.offer_count += 1
        
        return counter_offer
    
    def _calculate_acceptance_threshold(self, progress: float, current_offer_value: float) -> float:
        """Calculate the minimum value we'll accept based on negotiation progress"""
        # Base threshold decreases over time
        base_threshold = self.total_value * (
            self.initial_demand_ratio - (self.initial_demand_ratio - self.min_acceptable_ratio) * progress
        )
        
        # If opponent is making concessions, be more willing to accept
        if len(self.opponent_offers) >= 2:
            last_offer = self.opponent_offers[-1][1]
            prev_offer = self.opponent_offers[-2][1]
            if last_offer > prev_offer:
                # Opponent is conceding - slightly lower our threshold
                base_threshold *= 0.98
        
        # If we're getting our best offer yet, consider accepting
        if current_offer_value == self.best_offer_value and self.best_offer_value > 0:
            if len(self.opponent_offers) >= 3:
                # Recent offers are improving
                recent_trend = [
                    self.opponent_offers[i][1] for i in range(-3, 0)
                ]
                if recent_trend[-1] > recent_trend[0]:
                    base_threshold *= 0.97
        
        return base_threshold
    
    def _make_counter_offer(self, progress: float) -> list[int]:
        """Construct a strategic counter-offer"""
        # Calculate our target value based on progress
        target_ratio = self.initial_demand_ratio - (self.initial_demand_ratio - self.min_acceptable_ratio) * progress
        target_value = self.total_value * target_ratio
        
        # Build offer starting with most valuable items
        offer = [0] * self.n
        remaining = self.counts[:]
        current_value = 0
        
        # First pass: take items until we reach or exceed target
        for i in self.sorted_indices:
            if remaining[i] > 0 and current_value < target_value:
                # Take as many as needed of this item type
                needed = target_value - current_value
                if self.values[i] > 0:
                    take = min(remaining[i], (needed // self.values[i]) + 1)
                else:
                    take = 0
                take = min(take, remaining[i])
                offer[i] = take
                remaining[i] -= take
                current_value += take * self.values[i]
        
        # If we still haven't reached target, take remaining valuable items
        if current_value < target_value:
            for i in self.sorted_indices:
                if remaining[i] > 0 and self.values[i] > 0:
                    take = min(remaining[i], 1)  # Take one at a time
                    offer[i] += take
                    remaining[i] -= take
                    current_value += take * self.values[i]
                    if current_value >= target_value:
                        break
        
        # Strategic adjustment: if we're asking for too much (>80% of value),
        # reduce slightly to make it more acceptable
        if current_value > self.total_value * 0.80:
            # Give back least valuable items
            for i in self.sorted_indices[::-1]:  # Least valuable first
                if offer[i] > 0 and self.values[i] == min(self.values[i] for i in range(self.n)):
                    offer[i] -= 1
                    remaining[i] += 1
                    break
        
        return offer