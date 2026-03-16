class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.is_first = (me == 0)
        self.rounds_remaining = max_rounds
        self.opponent_valuations = [1] * len(counts)
        self.offer_history = []
        self.turn_count = 0
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # Update opponent valuation based on their offer
        if o is not None:
            self.rounds_remaining -= 1
            self.offer_history.append(o.copy())
            self._update_opponent_valuations()
            
            # Calculate value of opponent's offer
            our_value = sum(v * x for v, x in zip(self.values, o))
            
            # Should we accept?
            if self._should_accept(our_value):
                return None
        
        # Make our offer
        return self._make_offer()
    
    def _update_opponent_valuations(self):
        """Estimate opponent valuations more accurately"""
        n_items = len(self.counts)
        if len(self.offer_history) < 2:
            return
        
        # Get the last two offers from opponent
        last_offer = self.offer_history[-1]
        prev_offer = self.offer_history[-2] if len(self.offer_history) >= 2 else None
        
        # Calculate what the opponent kept in each offer
        last_opponent_get = [self.counts[i] - last_offer[i] for i in range(n_items)]
        
        # If opponent kept the same items in consecutive offers, likely valuable to them
        # If they reduced something, it's less valuable
        for i in range(n_items):
            if last_opponent_get[i] == self.counts[i]:  # Always keeps all
                self.opponent_valuations[i] = max(3, max(self.values) if max(self.values) > 0 else 1)
            elif last_opponent_get[i] == 0:  # Never keeps any
                self.opponent_valuations[i] = 0
            elif prev_offer and last_opponent_get[i] > 0 and self.counts[i] - prev_offer[i] > 0:
                # Kept in both offers, likely valuable
                self.opponent_valuations[i] = max(2, self.opponent_valuations[i])
            elif last_opponent_get[i] > 0:
                # Kept only in last offer, maybe valuable
                self.opponent_valuations[i] = max(1, self.opponent_valuations[i])
            else:
                # Reduced or eliminated in last offer, less valuable
                self.opponent_valuations[i] = max(0, self.opponent_valuations[i] - 1)
    
    def _should_accept(self, our_value: int) -> bool:
        """Determine if we should accept the current offer"""
        rounds_left = self.rounds_remaining
        if rounds_left <= 0:
            return True
        
        # Calculate minimum acceptable value based on remaining rounds
        # Be more selective early on, more willing to accept later
        # Consider who moves first as first mover has advantage
        if self.is_first:
            # As first mover, we should get more than half on average
            # But be more willing to accept as rounds decrease
            min_acceptable_ratio = 0.5 + 0.1 * (1 - rounds_left / self.max_rounds)
        else:
            # As second mover, we can wait for better offers
            # But risk getting nothing if negotiations fail
            min_acceptable_ratio = 0.4 + 0.15 * (1 - rounds_left / self.max_rounds)
            
        min_acceptable = int(self.total_value * min_acceptable_ratio)
        
        # If offer is good enough or we're very close to end, accept
        return our_value >= min_acceptable or rounds_left <= 1
    
    def _make_offer(self) -> list[int]:
        """Create a strategic offer"""
        n_items = len(self.counts)
        offer = [0] * n_items
        
        # Calculate target value for ourselves
        rounds_left = self.rounds_remaining
        
        # Adjust strategy based on position and rounds
        if self.is_first:
            # First mover: be more aggressive initially, gradually moderate
            target_ratio = 0.6 + 0.1 * (1 - rounds_left / self.max_rounds)
            target_ratio = min(0.7, max(0.5, target_ratio))
        else:
            # Second mover: be more moderate initially, more aggressive if needed
            target_ratio = 0.5 + 0.1 * (1 - rounds_left / self.max_rounds)
            target_ratio = min(0.6, max(0.4, target_ratio))
            
        target_value = int(self.total_value * target_ratio)
        
        # Sort items: prefer items we value highly and opponent likely values low
        items = list(range(n_items))
        
        def item_priority(i):
            our_val = self.values[i]
            opp_val = max(1, self.opponent_valuations[i])
            
            # High priority: high our value, low opponent value
            if our_val == 0:
                return -100  # Avoid items we don't value
            if opp_val == 0:
                return float('inf')  # Items opponent doesn't value, take all
            return our_val / opp_val
        
        items.sort(key=item_priority, reverse=True)
        
        # Take items until we reach target value
        current_value = 0
        for i in items:
            if current_value >= target_value:
                break
                
            item_value = self.counts[i] * self.values[i]
            
            # Don't take items with zero value to us unless necessary
            if self.values[i] == 0:
                continue
                
            offer[i] = self.counts[i]
            current_value += item_value
        
        # If we still don't have enough value, try to add some items we value less
        if current_value < target_value:
            for i in items:
                if offer[i] < self.counts[i]:
                    # Add items if they're valuable to us
                    needed_value = target_value - current_value
                    item_value = self.values[i]
                    
                    if item_value > 0:
                        num_to_add = min(self.counts[i] - offer[i], 
                                        (needed_value + item_value - 1) // item_value)
                        offer[i] += num_to_add
                        current_value += num_to_add * item_value
                        
                    if current_value >= target_value:
                        break
        
        # Ensure we don't end up with zero value if possible
        if current_value == 0 and self.total_value > 0:
            # Take at least one item with positive value
            for i in items:
                if self.values[i] > 0:
                    offer[i] = self.counts[i]
                    break
        
        # Ensure we don't exceed total items
        for i in range(n_items):
            if offer[i] > self.counts[i]:
                offer[i] = self.counts[i]
                
        return offer