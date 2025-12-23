class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.rounds_left = max_rounds * 2  # Total turns
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.my_turn = me
        self.turn_count = 0
        
        # Track opponent's likely preferences
        self.opponent_values = [0] * len(counts)
        self.offers_seen = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        turns_remaining = self.max_rounds * 2 - self.turn_count
        
        # If we received an offer, analyze it
        if o is not None:
            self.offers_seen.append(o)
            self._update_opponent_estimate(o)
            
            # Evaluate the offer
            my_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Accept if offer is good enough based on time pressure
            acceptance_threshold = self._get_acceptance_threshold(turns_remaining)
            
            if my_value >= acceptance_threshold * self.total_value:
                return None  # Accept
            
            # Accept any positive offer on the last turn
            if turns_remaining == 0 and my_value > 0:
                return None
        
        # Make a counter-offer
        return self._generate_offer(turns_remaining)
    
    def _update_opponent_estimate(self, o: list[int]):
        """Estimate opponent's values based on what they're asking for."""
        # Items they want more of are likely more valuable to them
        their_share = [self.counts[i] - o[i] for i in range(len(o))]
        
        # Update estimates (simple heuristic)
        for i in range(len(their_share)):
            if their_share[i] > 0:
                self.opponent_values[i] += their_share[i]
    
    def _get_acceptance_threshold(self, turns_remaining: int) -> float:
        """Calculate minimum acceptable value as fraction of total."""
        if turns_remaining <= 1:
            return 0.1  # Accept almost anything on last turn
        elif turns_remaining <= 3:
            return 0.4  # Be more flexible near the end
        elif turns_remaining <= 5:
            return 0.5  # Accept fair deals
        else:
            return 0.6  # Be greedy early on
    
    def _generate_offer(self, turns_remaining: int) -> list[int]:
        """Generate a strategic counter-offer."""
        # Start with a greedy baseline
        target_ratio = self._get_target_ratio(turns_remaining)
        
        # Try to find an offer that gives us our target while being strategic
        offer = self._find_strategic_split(target_ratio)
        
        # Ensure we're not offering more than available
        for i in range(len(offer)):
            offer[i] = min(offer[i], self.counts[i])
        
        return offer
    
    def _get_target_ratio(self, turns_remaining: int) -> float:
        """How much of total value we should aim for."""
        if turns_remaining <= 2:
            return 0.45  # Be very flexible at the end
        elif turns_remaining <= 4:
            return 0.55  # Moderate flexibility
        elif turns_remaining <= 6:
            return 0.65  # Still aiming high
        else:
            return 0.75  # Start greedy
    
    def _find_strategic_split(self, target_ratio: float) -> list[int]:
        """Find a split that aims for target_ratio of value."""
        target_value = target_ratio * self.total_value
        
        # Create a list of items sorted by value to me
        items = []
        for i in range(len(self.counts)):
            for _ in range(self.counts[i]):
                items.append((self.values[i], i))
        
        # Sort by my value (descending) but consider opponent preferences
        items.sort(key=lambda x: (
            x[0] - self.opponent_values[x[1]] * 0.1,  # Prefer items opponent values less
            -x[0]  # Then by my value
        ), reverse=True)
        
        # Take items greedily until we hit target
        offer = [0] * len(self.counts)
        current_value = 0
        
        for value, idx in items:
            if current_value < target_value or value > 0:
                offer[idx] += 1
                current_value += value
            
            if current_value >= target_value:
                break
        
        # If we haven't reached minimum acceptable, take more high-value items
        if current_value < 0.4 * self.total_value:
            for i in range(len(offer)):
                if self.values[i] > 0:
                    offer[i] = self.counts[i]
        
        return offer