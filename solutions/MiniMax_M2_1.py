class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        
        # Total value calculation
        self.total_value = sum(counts[i] * values[i] for i in range(self.n))
        self.total_moves = max_rounds * 2
        self.moves_left = self.total_moves
        
        # Sort items by value (descending)
        self.sorted_indices = sorted(range(self.n), key=lambda i: values[i], reverse=True)
        
        # Track opponent behavior
        self.best_offer_received = None
        self.best_offer_value = -1
        self.opponent_accepted_my_offer = False
        self.my_offer_history = []
        
        # Track if I'm the first player
        self.is_first = (me == 0)
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        """
        Called when it's my turn to act.
        o: The offer from the partner (what they give to me), or None if it's my opening.
        Returns: None to accept, or a list representing what I want for myself.
        """
        self.moves_left -= 1
        progress = 1 - (self.moves_left / self.total_moves)
        
        # If I received an offer, analyze it
        if o is not None:
            offered_value = sum(o[i] * self.values[i] for i in range(self.n))
            
            # Update tracking of best offer received
            if offered_value > self.best_offer_value:
                self.best_offer_value = offered_value
                self.best_offer_received = o[:]
            
            # Dynamic acceptance threshold
            # Start high (55%) and decrease gradually, but never below 45%
            min_acceptable = self.total_value * (0.55 - 0.1 * progress)
            min_acceptable = max(min_acceptable, self.total_value * 0.45)
            
            # Check if opponent is conceding (offer is better than before)
            improving = False
            if len(self.my_offer_history) > 0:
                last_offer_value = self._calculate_value(self.my_offer_history[-1])
                if offered_value > last_offer_value:
                    improving = True
            
            # Accept if offer meets threshold OR opponent is improving significantly
            if offered_value >= min_acceptable or (improving and offered_value >= min_acceptable * 0.95):
                return None
            
            # Special case: last move - accept if offer is reasonable
            if self.moves_left <= 1:
                if offered_value >= self.total_value * 0.40:
                    return None
                # On last move, make one final offer
                if self.moves_left == 0:
                    return None
        
        # Make a counter-offer
        # Calculate my target value based on progress
        target = self.total_value * (0.60 - 0.10 * progress)
        target = max(target, self.total_value * 0.50)
        
        # Build the offer
        my_offer = self._build_counter_offer(target)
        self.my_offer_history.append(my_offer)
        
        return my_offer
    
    def _calculate_value(self, offer: list[int]) -> float:
        """Calculate the value of an offer to me"""
        return sum(offer[i] * self.values[i] for i in range(self.n))
    
    def _build_counter_offer(self, target_value: float) -> list[int]:
        """
        Constructs a counter-offer targeting a specific value.
        Uses a strategic approach to maximize value while being acceptable.
        """
        offer = [0] * self.n
        remaining = self.counts[:]
        current_value = 0
        
        # First pass: take the most valuable items first
        for i in self.sorted_indices:
            if remaining[i] > 0:
                take = min(remaining[i], 1)
                offer[i] = take
                remaining[i] -= take
                current_value += take * self.values[i]
        
        # Second pass: if needed, take more items to reach target
        if current_value < target_value:
            for i in self.sorted_indices:
                while remaining[i] > 0 and current_value < target_value:
                    offer[i] += 1
                    remaining[i] -= 1
                    current_value += self.values[i]
        
        # Final adjustment: ensure the offer is valid
        # This gives partner what's left: [counts[i] - offer[i] for i in range(self.n)]
        return offer