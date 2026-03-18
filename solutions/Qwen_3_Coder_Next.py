class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.opponent_total = self.total_value  # Assumption: same total value for opponent
        
        # State tracking
        self.round_num = 0
        self.last_opponent_offer = None
        self.offer_history = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        # Update round counter
        if o is not None:
            self.round_num += 1
            self.last_opponent_offer = o.copy()
            self.offer_history.append(o.copy())
        
        # Calculate remaining rounds (including this one if we make an offer)
        rounds_left = self.max_rounds - self.round_num
        
        # Calculate our value for any potential offer
        if o is not None:
            our_value_from_offer = sum(v * x for v, x in zip(self.values, o))
        else:
            our_value_from_offer = None
        
        # Determine if we should accept the opponent's offer
        if o is not None and self._should_accept(o, rounds_left):
            return None
            
        # Make our best offer
        return self._make_strategic_offer(rounds_left)
    
    def _should_accept(self, opponent_offer: list[int], rounds_left: int) -> bool:
        """Determine if we should accept the opponent's offer."""
        our_value = sum(v * x for v, x in zip(self.values, opponent_offer))
        
        # If no rounds left, must accept
        if rounds_left <= 0:
            return True
            
        # Calculate the minimum value we'd get if we continue
        # Use game theory: in the final round, the mover has advantage
        # Assume we can get at least half the remaining value if we continue
        min_future_value = self.total_value * 0.4
        
        # Be more willing to accept as rounds decrease
        acceptance_threshold = min_future_value * (0.5 + rounds_left / (2 * self.max_rounds))
        
        return our_value >= acceptance_threshold
    
    def _make_strategic_offer(self, rounds_left: int) -> list[int]:
        """Create an offer that the opponent is likely to accept."""
        n_items = len(self.counts)
        
        # Estimate opponent values based on their past behavior
        opponent_estimate = self._estimate_opponent_values()
        
        # Calculate total value for opponent with estimated values
        opponent_total_estimate = sum(c * v for c, v in zip(self.counts, opponent_estimate))
        
        # Target split: try to give opponent just enough to accept
        # First mover should get more, second mover can be more demanding
        if self.me == 0:  # First mover
            # Offer opponent about 45-55% depending on rounds
            opponent_target_ratio = 0.45 + 0.1 * (1 - rounds_left / self.max_rounds)
        else:  # Second mover
            # Can be more demanding as we've seen their offers
            opponent_target_ratio = 0.4 + 0.15 * (1 - rounds_left / self.max_rounds)
            
        opponent_target_value = int(opponent_total_estimate * opponent_target_ratio)
        
        # Create offer that minimizes what we give while meeting opponent's target
        offer = [0] * n_items
        opponent_get_value = 0
        
        # Sort items by how "expensive" they are for the opponent (high value to them, low to us)
        # We want to give them items that are valuable to them but not to us
        items = list(range(n_items))
        
        def item_cost(i):
            our_val = self.values[i]
            opp_val = opponent_estimate[i]
            
            # Avoid giving items we value highly
            if our_val > 0 and opp_val == 0:
                return float('-inf')  # Don't give these to opponent
            if our_val == 0 and opp_val > 0:
                return float('inf')  # These are perfect for giving
            if opp_val == 0:
                return 0  # Items opponent doesn't want
            # Balance: give items where opponent values highly relative to us
            return opp_val / max(1, our_val)
        
        items.sort(key=item_cost, reverse=True)
        
        # Give items to opponent until they reach target value
        for i in items:
            if opponent_get_value >= opponent_target_value:
                break
                
            # Skip items we value highly if opponent doesn't
            if self.values[i] > 0 and opponent_estimate[i] == 0:
                continue
                
            offer[i] = self.counts[i]
            opponent_get_value += self.counts[i] * opponent_estimate[i]
        
        # If we still need to give more value, give items where both value equally
        if opponent_get_value < opponent_target_value:
            for i in items:
                if offer[i] < self.counts[i] and opponent_estimate[i] > 0:
                    needed = opponent_target_value - opponent_get_value
                    items_to_add = min(self.counts[i] - offer[i], 
                                      (needed + opponent_estimate[i] - 1) // opponent_estimate[i])
                    offer[i] += items_to_add
                    opponent_get_value += items_to_add * opponent_estimate[i]
                    
                if opponent_get_value >= opponent_target_value:
                    break
        
        # Ensure we don't end with zero value
        our_value_in_offer = sum(v * x for v, x in zip(self.values, offer))
        if our_value_in_offer == 0 and self.total_value > 0:
            # Give opponent minimal amount while keeping something for ourselves
            # Find items we value that opponent values less
            best_item = max(range(n_items), 
                          key=lambda i: self.values[i] - opponent_estimate[i])
            for i in items:
                if self.values[i] > 0 and opponent_estimate[i] == 0:
                    offer[i] = self.counts[i]
                    break
            
        # Validate offer
        for i in range(n_items):
            if offer[i] > self.counts[i]:
                offer[i] = self.counts[i]
                
        return offer
    
    def _estimate_opponent_values(self) -> list[int]:
        """Estimate opponent valuations based on their behavior."""
        n_items = len(self.counts)
        
        # Initialize with uniform values (conservative)
        estimate = [1] * n_items
        
        if not self.offer_history:
            return estimate
            
        # Analyze opponent's offers to see what they wanted
        # Look at what they kept in their offers
        for offer in self.offer_history:
            for i in range(n_items):
                kept = self.counts[i] - offer[i]
                
                # If opponent kept many items of this type, likely valuable
                if kept > self.counts[i] * 0.7:
                    estimate[i] = max(estimate[i], 3)
                elif kept > self.counts[i] * 0.3:
                    estimate[i] = max(estimate[i], 2)
        
        # Refine estimates based on how much the opponent persisted
        # If they kept offering the same thing, likely a firm position
        if len(self.offer_history) >= 2:
            # Check consistency across offers
            for i in range(n_items):
                offers_consistent = True
                base_kept = self.counts[i] - self.offer_history[0][i]
                
                for offer in self.offer_history[1:]:
                    current_kept = self.counts[i] - offer[i]
                    if current_kept != base_kept:
                        offers_consistent = False
                        break
                
                if offers_consistent and base_kept > 0:
                    estimate[i] = max(estimate[i], 2)
        
        # Adjust based on which items we value highly vs. what they offered
        # If they consistently refused items we value, they likely value them more
        for i in range(n_items):
            if self.values[i] > 0:
                refusals = 0
                total_offers = len(self.offer_history)
                
                for offer in self.offer_history:
                    if offer[i] == 0:  # They refused to give us this item
                        refusals += 1
                
                if refusals > total_offers * 0.7 and self.values[i] > 0:
                    # They kept items we want - likely valuable to them
                    estimate[i] = max(estimate[i], 3)
        
        return estimate