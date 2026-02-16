class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.rounds_remaining = max_rounds
        self.is_first = (me == 0)
        self.opponent_offer_history = []
        self.last_opponent_offer = None

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds_remaining -= 1
        
        # Update opponent history if we received an offer
        if o is not None:
            self.last_opponent_offer = o
            # Store opponent's take (what they kept for themselves)
            opponent_take = [self.counts[i] - o[i] for i in range(len(self.counts))]
            self.opponent_offer_history.append(opponent_take)
        
        # If it's our first turn (no offer to respond to)
        if o is None:
            return self._make_initial_offer()
        
        # Calculate current offer value to us
        our_value = sum(v * x for v, x in zip(self.values, o))
        
        # If opponent's offer is good enough, accept it
        if self._should_accept(o):
            return None
        
        # Otherwise, make a counter-offer
        return self._make_counter_offer()

    def _should_accept(self, offer: list[int]) -> bool:
        """Determine if we should accept the current offer"""
        our_value = sum(v * x for v, x in zip(self.values, offer))
        
        # Calculate what we'd get if we walk away (0) or continue negotiating
        # Estimate the minimum acceptable offer we could get in future rounds
        
        # In early rounds, be more selective
        if self.rounds_remaining >= 5:
            # Accept if offer gives us >45% of total value
            return our_value >= self.total_value * 0.45
        
        # In mid rounds, be more willing to accept reasonable offers
        if self.rounds_remaining >= 2:
            # Accept if offer gives us >40% of total value
            return our_value >= self.total_value * 0.40
        
        # In final rounds, be very willing to accept decent offers to avoid no deal
        if self.rounds_remaining == 1:
            # Accept if offer gives us >30% of total value (at least something is better than nothing)
            return our_value >= self.total_value * 0.30
        
        # Very last resort - accept any positive offer
        return our_value > 0

    def _estimate_opponent_values(self) -> list[int]:
        """Estimate opponent's valuations based on their offers"""
        estimates = [0] * len(self.counts)
        
        # If we have opponent offer history, analyze it
        if self.opponent_offer_history:
            # Count how many times opponent took each item type
            for take in self.opponent_offer_history:
                for i, count in enumerate(take):
                    if count > 0:
                        # Assume opponent values items they consistently take
                        estimates[i] += count
            
            # Normalize estimates based on relative frequency
            max_estimate = max(estimates) if max(estimates) > 0 else 1
            if max_estimate > 0:
                estimates = [max(1, int(e * 10 / max_estimate)) for e in estimates]
        else:
            # Default: assume opponent values similar to us but reversed
            estimates = [max(1, self.values[i]) for i in range(len(self.counts))]
        
        return estimates

    def _make_initial_offer(self) -> list[int]:
        """Create initial offer if we go first"""
        estimates = self._estimate_opponent_values()
        
        offer = [0] * len(self.counts)
        # Sort items by our value to opponent ratio (take high value to us, low to them)
        item_scores = [(i, self.values[i] / max(estimates[i], 1)) 
                      for i in range(len(self.counts))]
        item_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Give opponent their most valued items
        for i, _ in item_scores:
            if estimates[i] > 0 and self.counts[i] > 0:
                # Give opponent ~40% of items they value highly
                give_opponent = max(1, (self.counts[i] * 3) // 5)
                offer[i] = self.counts[i] - give_opponent
            else:
                # Take all items opponent doesn't value
                offer[i] = self.counts[i]
        
        return offer

    def _make_counter_offer(self) -> list[int]:
        """Create counter-offer after receiving opponent's offer"""
        estimates = self._estimate_opponent_values()
        
        offer = [0] * len(self.counts)
        
        # Sort items by our value to opponent ratio
        item_scores = [(i, self.values[i] / max(estimates[i], 1)) 
                      for i in range(len(self.counts))]
        item_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Determine how generous to be based on rounds remaining
        if self.rounds_remaining <= 2:
            # Last rounds: be very generous
            generosity_factor = 0.6  # Give opponent 60% of valuable items
        elif self.rounds_remaining <= 4:
            # Mid rounds: be somewhat generous
            generosity_factor = 0.5
        else:
            # Early rounds: be moderately generous
            generosity_factor = 0.4
        
        # Distribute items strategically
        for i, _ in item_scores:
            if estimates[i] > 0 and self.counts[i] > 0:
                # Give opponent their most valued items based on generosity factor
                give_opponent = int(self.counts[i] * generosity_factor)
                give_opponent = max(1, give_opponent)  # Always give at least 1 if they value it
                offer[i] = self.counts[i] - give_opponent
            else:
                # Take all items opponent doesn't value
                offer[i] = self.counts[i]
        
        # Make sure we're not being too greedy in late rounds
        if self.rounds_remaining <= 3:
            # If we're taking too much, reduce our take
            our_value = sum(v * x for v, x in zip(self.values, offer))
            if our_value > self.total_value * 0.7:
                # Reduce our take on items opponent values
                for i, _ in item_scores:
                    if estimates[i] > 0 and offer[i] > 0 and our_value > self.total_value * 0.7:
                        reduce_by = min(offer[i], (offer[i] + 1) // 2)
                        offer[i] -= reduce_by
        
        return offer