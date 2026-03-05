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
        if not self.offer_history:
            return
            
        # Calculate how much opponent got in each offer
        opponent_gets = []
        for offer in self.offer_history:
            opponent_get = [self.counts[i] - offer[i] for i in range(n_items)]
            opponent_gets.append(opponent_get)
        
        # Simple heuristic: if opponent kept an item across multiple offers, 
        # it's likely valuable to them
        kept_counts = [0] * n_items
        total_offers = len(self.offer_history)
        
        for opponent_get in opponent_gets:
            for i in range(n_items):
                if opponent_get[i] > 0:
                    kept_counts[i] += 1
        
        # Estimate valuations based on how often opponent kept items
        max_val = max(self.values) if max(self.values) > 0 else 1
        for i in range(n_items):
            if total_offers > 0:
                ratio = kept_counts[i] / total_offers
                if ratio > 0.8:
                    self.opponent_valuations[i] = max(1, max_val)
                elif ratio > 0.5:
                    self.opponent_valuations[i] = max(1, max_val // 2)
                elif ratio > 0.2:
                    self.opponent_valuations[i] = max(1, max_val // 3)
                else:
                    self.opponent_valuations[i] = 1
            else:
                self.opponent_valuations[i] = 1
    
    def _should_accept(self, our_value: int) -> bool:
        """Determine if we should accept the current offer"""
        # Calculate minimum acceptable value based on remaining rounds
        # Be more willing to accept as rounds decrease
        rounds_left = self.rounds_remaining
        
        if rounds_left <= 1:
            return our_value > 0
            
        # Calculate proportion of value we'd likely get if we continue
        # As rounds decrease, our bargaining power decreases
        if self.is_first:
            # First mover has advantage initially but loses it faster
            min_acceptable_ratio = max(0.3, 0.7 - 0.05 * (self.max_rounds - rounds_left))
        else:
            # Second mover waits and can be more selective
            min_acceptable_ratio = max(0.3, 0.55 - 0.03 * (self.max_rounds - rounds_left))
        
        min_acceptable = int(self.total_value * min_acceptable_ratio)
        
        return our_value >= min_acceptable
    
    def _make_offer(self) -> list[int]:
        """Create a strategic offer"""
        n_items = len(self.counts)
        offer = [0] * n_items
        
        # Calculate target value for ourselves
        rounds_left = self.rounds_remaining
        if self.is_first:
            # First mover: be more aggressive initially
            target_ratio = max(0.6, min(0.7 - 0.02 * (self.max_rounds - rounds_left), 0.7))
        else:
            # Second mover: be more moderate
            target_ratio = max(0.5, min(0.55 - 0.015 * (self.max_rounds - rounds_left), 0.6))
            
        target_value = int(self.total_value * target_ratio)
        
        # Sort items by comparative advantage (our value vs opponent value)
        items = list(range(n_items))
        opp_vals = self.opponent_valuations
        
        # If opponent valuation is not set, use a reasonable default
        if not opp_vals or any(v == 1 for v in opp_vals):
            opp_vals = [1] * n_items
        
        def comparative_advantage(i):
            our_val = self.values[i]
            opp_val = max(1, opp_vals[i])
            # If our value is high and opponent's is low, we should take it
            if our_val > 0 and opp_val == 0:
                return float('inf')
            return our_val / opp_val
        
        # Sort items: prefer items with high our value and low opponent value
        items.sort(key=comparative_advantage, reverse=True)
        
        # Take items until we reach target value
        current_value = 0
        for i in items:
            if current_value >= target_value:
                break
                
            item_value = self.counts[i] * self.values[i]
            
            # Don't take items with zero value to us unless necessary
            if self.values[i] == 0 and current_value > 0:
                continue
                
            offer[i] = self.counts[i]
            current_value += item_value
        
        # If we still don't have enough value, add items we value less
        if current_value < target_value:
            for i in items:
                if offer[i] < self.counts[i]:
                    # Add some of this item type
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