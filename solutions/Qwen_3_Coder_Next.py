class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.rounds_remaining = max_rounds
        self.is_first = (me == 0)
        self.opponent_valuation = None
        self.last_opponent_offer = None
        self.opponent_type = None  # 'aggressive', 'fair', 'patient'

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds_remaining -= 1
        
        # Update opponent valuation if we have previous offers
        if o is not None:
            self.last_opponent_offer = o
            
        # If we have an offer to evaluate, decide whether to accept
        if o is not None:
            our_value = sum(v * x for v, x in zip(self.values, o))
            
            # Calculate what the opponent likely values
            opponent_val = {}
            for i, val in enumerate(self.values):
                opponent_val[i] = self._estimate_opponent_value(i)
            
            # Estimate opponent's value from current offer
            their_value_from_offer = sum(opponent_val.get(i, 0) * (self.counts[i] - o[i]) 
                                       for i in range(len(self.counts)))
            
            # Accept if offer gives us reasonable value AND opponent gets reasonable value
            # (to incentivize agreement)
            if our_value >= self.total_value * 0.4 and their_value_from_offer >= 0:
                # Check if we're in late rounds and need to secure a deal
                if self.rounds_remaining <= 2 and our_value >= self.total_value * 0.3:
                    return None
                # Also accept if it's better than what we can likely get
                if our_value >= self.total_value * 0.45:
                    return None
                    
            # If opponent's offer is generous (gives us > half), definitely accept
            if our_value >= self.total_value * 0.6:
                return None

        # Generate our counter-offer
        # First, estimate what the opponent values
        opponent_estimates = self._estimate_opponent_values()
        
        # Sort items by our value (descending) but consider opponent estimates
        item_indices = list(range(len(self.counts)))
        # Score each item: high value to us, low value to opponent = better to take
        item_scores = [(i, self.values[i] * 2 - opponent_estimates.get(i, 0)) 
                      for i in item_indices]
        item_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Create our offer: take items with highest scores, but leave some for opponent
        offer = [0] * len(self.counts)
        total_to_give = sum(self.counts) - sum(offer)
        
        # Calculate how much we need to give to opponent to make it acceptable
        # Start by giving opponent their most valuable items
        opponent_items = sorted(item_indices, key=lambda i: opponent_estimates.get(i, 0), reverse=True)
        
        # Distribute items strategically
        for idx in opponent_items:
            # Give opponent their most valued items up to reasonable amount
            if opponent_estimates.get(idx, 0) > 0:
                # Give opponent about 1/3 to 1/2 of each valuable item type
                give_opponent = (self.counts[idx] + 1) // 2 if self.rounds_remaining > 15 else max(1, (self.counts[idx] * 2) // 3)
                give_opponent = min(give_opponent, self.counts[idx])
                offer[idx] = self.counts[idx] - give_opponent
            else:
                # Take all of items opponent doesn't value
                offer[idx] = self.counts[idx]
        
        # Adjust based on rounds remaining
        if self.rounds_remaining <= 2:
            # Late game: be more generous to ensure agreement
            for idx in opponent_items:
                if opponent_estimates.get(idx, 0) > 0 and offer[idx] < self.counts[idx]:
                    offer[idx] = min(offer[idx] + 1, self.counts[idx])
        
        return offer
    
    def _estimate_opponent_values(self) -> dict:
        """Estimate opponent's valuations based on patterns from previous rounds"""
        estimates = {}
        
        if self.last_opponent_offer is not None:
            # Simple heuristic: items the opponent took in their offer are likely valuable to them
            for i in range(len(self.counts)):
                their_taken = self.counts[i] - self.last_opponent_offer[i]
                if their_taken > 0:
                    # Assume they value items they took highly
                    estimates[i] = max(1, self.values[i])
                else:
                    estimates[i] = 0
        
        # Default estimates: if we have no info, assume opponent values similarly
        if not estimates:
            estimates = {i: self.values[i] for i in range(len(self.counts))}
        
        # Ensure at least minimal value for all items with count > 0
        for i in range(len(self.counts)):
            if self.counts[i] > 0 and estimates.get(i, 0) == 0:
                estimates[i] = 1  # Give minimal value to ensure negotiation
        
        return estimates
    
    def _estimate_opponent_value(self, idx: int) -> int:
        """Estimate opponent's value for a specific item type"""
        estimates = self._estimate_opponent_values()
        return estimates.get(idx, 1)