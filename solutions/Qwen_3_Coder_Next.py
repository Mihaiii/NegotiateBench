class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.rounds_remaining = max_rounds
        self.is_first = (me == 0)
        self.opponent_valuations = None  # Will be learned during negotiation
        self.offer_history = []
        self.opponent_kept_counts = [0] * len(counts)
        self.opponent_gave_counts = [0] * len(counts)
        self.turn_count = 0
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # Record opponent's offer for analysis
        if o is not None:
            self.offer_history.append(o.copy())
            # Update our estimate of opponent valuations
            self._update_opponent_valuations(o)
        
        # Estimate opponent valuations (use latest info)
        self._estimate_opponent_valuation()
        
        # On first turn, make an initial offer
        if o is None:
            return self._make_initial_offer()
        
        # Calculate what we're getting in this offer
        our_value = sum(v * x for v, x in zip(self.values, o))
        
        # Calculate what opponent is getting in this offer
        their_value = self._calculate_opponent_value(o)
        
        # Determine if we should accept
        if self._should_accept(our_value, their_value):
            return None
        
        # Make counter-offer
        return self._make_counter_offer()
    
    def _update_opponent_valuations(self, offer):
        """Update estimates based on opponent's offer"""
        for i in range(len(self.counts)):
            if offer[i] == self.counts[i]:  # Opponent kept all of item i
                self.opponent_kept_counts[i] += 1
            elif offer[i] == 0:  # Opponent gave all of item i to us
                self.opponent_gave_counts[i] += 1
    
    def _estimate_opponent_valuation(self):
        """Estimate opponent valuations from behavior"""
        if not self.offer_history:
            # Default: assume opponent values items somewhat differently
            # Use a simple heuristic: items we value highly might be less valuable to them
            self.opponent_valuations = [max(1, max(1, (self.total_value - self.values[i] * self.counts[i]) // max(1, sum(self.counts) - self.counts[i]))) 
                                        for i in range(len(self.counts))]
            return
        
        # Count how many times opponent kept vs gave each item
        total_offers = len(self.offer_history)
        
        # Start with a baseline estimate
        self.opponent_valuations = [1] * len(self.counts)
        
        # Use offered counts to infer relative value
        # If opponent kept item i frequently but gave it up rarely, it's valuable to them
        for i in range(len(self.counts)):
            if self.opponent_kept_counts[i] > 0:
                # If opponent kept this item, estimate value based on how often they did so
                # and our knowledge that it has some value to them
                ratio = self.opponent_kept_counts[i] / total_offers
                # Start with a base and adjust based on keeping frequency
                base_val = max(1, self.values[i])
                if ratio > 0.7:
                    self.opponent_valuations[i] = max(base_val, int(base_val * 2.5))
                elif ratio > 0.4:
                    self.opponent_valuations[i] = max(base_val, int(base_val * 1.5))
                else:
                    self.opponent_valuations[i] = base_val
            elif self.opponent_gave_counts[i] > 0:
                # If opponent gave this item up frequently, it's likely low value to them
                self.opponent_valuations[i] = max(1, self.values[i] // 2)
        
        # Fallback to our values if estimates are too low
        for i in range(len(self.counts)):
            if self.opponent_valuations[i] <= 0:
                self.opponent_valuations[i] = 1
    
    def _calculate_opponent_value(self, offer):
        """Calculate how much the opponent gets in this offer"""
        if self.opponent_valuations is None:
            self._estimate_opponent_valuation()
        
        their_items = [self.counts[i] - offer[i] for i in range(len(self.counts))]
        return sum(v * x for v, x in zip(self.opponent_valuations, their_items))
    
    def _make_initial_offer(self) -> list[int]:
        """Create initial offer if we go first"""
        offer = [0] * len(self.counts)
        
        # Target value based on rounds remaining and whether we go first
        # Going first gives advantage, so we can aim higher
        if self.rounds_remaining >= 6:
            target_ratio = 0.7 if self.is_first else 0.6
        elif self.rounds_remaining >= 4:
            target_ratio = 0.6 if self.is_first else 0.55
        else:
            target_ratio = 0.55 if self.is_first else 0.50
        
        target = int(self.total_value * target_ratio)
        current_value = 0
        
        # Sort items by our value per opponent value ratio (descending)
        # Prefer keeping items where we have high relative value
        items = list(enumerate(self.values))
        
        def comparative_advantage(i):
            our_val = self.values[i]
            opp_val = self.opponent_valuations[i] if self.opponent_valuations else 1
            return our_val / max(1, opp_val)
        
        items.sort(key=lambda x: comparative_advantage(x[0]), reverse=True)
        
        # First, take all items where we have strong comparative advantage
        for i, our_val in items:
            if current_value >= target:
                break
                
            # If our value is much higher than opponent's, keep it
            opp_val = self.opponent_valuations[i] if self.opponent_valuations else 1
            if our_val > opp_val * 1.2:  # At least 20% higher value
                offer[i] = self.counts[i]
                current_value += self.counts[i] * our_val
        
        # If we still need more value, be more strategic about concessions
        if current_value < target:
            # Calculate how much more we need
            deficit = target - current_value
            
            # Sort remaining items by our value
            remaining_items = [(i, self.values[i]) for i in range(len(self.counts)) if offer[i] < self.counts[i]]
            remaining_items.sort(key=lambda x: x[1], reverse=True)
            
            for i, our_val in remaining_items:
                if current_value >= target:
                    break
                if our_val > 0:
                    # Take as many as needed to reach target
                    take = min(self.counts[i] - offer[i], (deficit + our_val - 1) // our_val)
                    offer[i] += take
                    current_value += take * our_val
        
        # Ensure we don't exceed total counts
        for i in range(len(offer)):
            offer[i] = min(offer[i], self.counts[i])
        
        return offer
    
    def _make_counter_offer(self) -> list[int]:
        """Create counter-offer after receiving opponent's offer"""
        offer = [0] * len(self.counts)
        
        # Target value based on rounds remaining
        if self.rounds_remaining <= 1:
            target_ratio = 0.35
        elif self.rounds_remaining <= 3:
            target_ratio = 0.45
        elif self.rounds_remaining <= 5:
            target_ratio = 0.55
        else:
            target_ratio = 0.65
        
        target = int(self.total_value * target_ratio)
        current_value = 0
        
        # Get opponent's latest offer to see what they want
        last_opponent_offer = self.offer_history[-1] if self.offer_history else [0] * len(self.counts)
        
        # Calculate opponent's requests (what they want from us)
        opponent_wants = [self.counts[i] - last_opponent_offer[i] for i in range(len(self.counts))]
        
        # Sort items by comparative advantage (descending)
        items = list(enumerate(self.values))
        items.sort(key=lambda x: self.values[x[0]] / max(1, self.opponent_valuations[x[0]] if self.opponent_valuations else 1), reverse=True)
        
        # First, take items where we have comparative advantage
        for i, our_val in items:
            if current_value >= target:
                break
                
            opp_val = self.opponent_valuations[i] if self.opponent_valuations else 1
            if our_val > opp_val:
                offer[i] = self.counts[i]
                current_value += self.counts[i] * our_val
        
        # If we need more value, consider opponent's requests
        if current_value < target:
            # Look at items opponent wants from us
            items_sorted_by_our_value = list(enumerate(self.values))
            items_sorted_by_our_value.sort(key=lambda x: x[1], reverse=True)
            
            for i, our_val in items_sorted_by_our_value:
                if current_value >= target:
                    break
                if offer[i] < self.counts[i]:
                    # Calculate how many more we could take
                    take = min(self.counts[i] - offer[i], (target - current_value) // max(1, our_val) + 1)
                    offer[i] += take
                    current_value += take * our_val
        
        # Late-game concession strategy: be more flexible
        if self.rounds_remaining <= 2 and current_value < target:
            # Look for items opponent values highly but we don't
            for i in range(len(offer)):
                if self.opponent_valuations and self.opponent_valuations[i] > self.values[i] * 2:
                    # Consider giving opponent more of this item in exchange for something better
                    # For now, just ensure we have a reasonable offer
                    pass
        
        return offer
    
    def _should_accept(self, our_value: int, their_value: int) -> bool:
        """Determine if we should accept the current offer"""
        # Calculate the minimum acceptable value based on rounds remaining
        # More rounds = we can be more selective
        if self.rounds_remaining <= 1:
            min_acceptable_ratio = 0.35
        elif self.rounds_remaining <= 3:
            min_acceptable_ratio = 0.45
        elif self.rounds_remaining <= 5:
            min_acceptable_ratio = 0.50
        elif self.rounds_remaining <= 8:
            min_acceptable_ratio = 0.55
        else:
            min_acceptable_ratio = 0.60
        
        min_acceptable = int(self.total_value * min_acceptable_ratio)
        
        # Also consider the threat point - what we'd get if we walk away
        # In future rounds, we might get less due to discounting
        future_value = 0
        if self.rounds_remaining > 0:
            # Estimate future value based on what we could get in a fair split
            future_value = int(self.total_value * 0.45)
        
        # Accept if we get at least our minimum acceptable value AND it's better than walking away
        return our_value >= max(min_acceptable, future_value) and our_value >= int(self.total_value * 0.35)