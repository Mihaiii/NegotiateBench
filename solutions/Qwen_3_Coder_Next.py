class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.is_first = (me == 0)
        self.rounds_remaining = max_rounds
        self.opponent_valuations = None
        self.offer_history = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        # Update rounds remaining - actually decrement on our turn only
        if o is not None:
            self.rounds_remaining -= 1
        
        # Record opponent's offer if provided (only if we're not first)
        if o is not None and not self.is_first:
            self.offer_history.append(o.copy())
        elif o is not None and self.is_first:
            # We're second, record what opponent offered to us
            self.offer_history.append(o.copy())
        
        # Estimate opponent valuations from history
        self._update_opponent_valuations()
        
        # If it's our first turn (o is None), make initial offer
        if o is None:
            return self._make_initial_offer()
        
        # Calculate our value for the opponent's offer
        our_value = sum(v * x for v, x in zip(self.values, o))
        
        # Determine if we should accept
        if self._should_accept(our_value):
            return None  # Accept
        
        # Make counter-offer
        return self._make_counter_offer()
    
    def _update_opponent_valuations(self):
        """Estimate opponent valuations based on their past offers"""
        if not self.offer_history:
            # Default estimate: assume opponent values items differently
            n_items = len(self.counts)
            self.opponent_valuations = [max(1, (self.total_value // n_items) // 2) for _ in range(n_items)]
            return
            
        n_items = len(self.counts)
        # Initialize with some baseline
        self.opponent_valuations = [1] * n_items
        
        # Analyze opponent's behavior: what did they keep vs give up?
        kept_counts = [0] * n_items
        total_counts = [0] * n_items
        
        for offer in self.offer_history:
            for i in range(n_items):
                # Opponent kept what we didn't get
                kept = self.counts[i] - offer[i]
                kept_counts[i] += kept
                total_counts[i] += self.counts[i]
        
        # Estimate valuations based on how much opponent kept each item
        for i in range(n_items):
            if total_counts[i] == 0:
                self.opponent_valuations[i] = 1
                continue
                
            ratio = kept_counts[i] / total_counts[i]
            
            # Use a more nuanced estimation based on how much opponent kept
            if ratio > 0.9:
                self.opponent_valuations[i] = max(3, self.values[i] + 2)
            elif ratio > 0.7:
                self.opponent_valuations[i] = max(2, self.values[i] + 1)
            elif ratio > 0.4:
                self.opponent_valuations[i] = max(1, self.values[i])
            elif ratio > 0.2:
                self.opponent_valuations[i] = max(1, self.values[i] - 1)
            else:
                self.opponent_valuations[i] = 1
    
    def _should_accept(self, our_value: int) -> bool:
        """Determine if we should accept the current offer"""
        # If we're out of rounds, accept anything with positive value
        if self.rounds_remaining <= 1:
            return our_value > 0
            
        # Calculate minimum acceptable value based on remaining rounds
        # Be more aggressive when we have more rounds
        if self.rounds_remaining <= 3:
            min_acceptable = max(1, int(self.total_value * 0.35))
        elif self.rounds_remaining <= 6:
            min_acceptable = max(1, int(self.total_value * 0.45))
        elif self.rounds_remaining <= 10:
            min_acceptable = max(1, int(self.total_value * 0.5))
        else:
            min_acceptable = max(1, int(self.total_value * 0.55))
        
        # Adjust based on whether this is our first offer or a response
        if not self.is_first and len(self.offer_history) == 1:
            # This is our first response - be more patient
            min_acceptable = max(min_acceptable, int(self.total_value * 0.4))
        
        # Check if opponent seems very flexible (gave us more than expected)
        # This is a signal they might accept less in return
        if self.opponent_valuations:
            opponent_value = self._calculate_opponent_value_from_our_view()
            if our_value >= min_acceptable and opponent_value > self.total_value * 0.65:
                return True
        
        return our_value >= min_acceptable
    
    def _calculate_opponent_value_from_our_view(self) -> int:
        """Estimate opponent's value for an offer from our perspective"""
        if not self.opponent_valuations or not self.offer_history:
            return self.total_value // 2
            
        # Look at last offer opponent made
        last_offer = self.offer_history[-1] if self.offer_history else [0] * len(self.counts)
        # Opponent gets what we didn't get in their offer
        opponent_gets = [self.counts[i] - last_offer[i] for i in range(len(self.counts))]
        return sum(v * x for v, x in zip(self.opponent_valuations, opponent_gets))
    
    def _make_initial_offer(self) -> list[int]:
        """Create initial offer (we get first turn)"""
        offer = [0] * len(self.counts)
        
        # Calculate how much value we want to keep for ourselves
        # First mover advantage - aim for more than 50%
        if self.is_first:
            target_ratio = 0.6  # Be aggressive as first mover
        else:
            target_ratio = 0.55
            
        target_value = int(self.total_value * target_ratio)
        
        # Sort items by our value to opponent value ratio (descending)
        items = list(range(len(self.counts)))
        opp_vals = self.opponent_valuations if self.opponent_valuations else [1] * len(self.counts)
        items.sort(key=lambda i: self.values[i] / max(1, opp_vals[i]), reverse=True)
        
        # Allocate items to reach target value
        current_value = 0
        for i in items:
            item_value = self.counts[i] * self.values[i]
            
            # If adding this item would exceed target by too much, try a smaller offer
            if current_value + item_value > target_value * 1.2 and current_value >= target_value * 0.9:
                # Try to add just what we need
                needed_value = target_value - current_value
                if needed_value <= item_value:
                    # We can potentially add partial, but since we can't split items, skip
                    continue
                    
            offer[i] = self.counts[i]
            current_value += item_value
            
            # If we've reached target and added value is reasonable, stop
            if current_value >= target_value and current_value <= target_value * 1.1:
                break
        
        # Ensure we don't end up with zero value if we can avoid it
        if current_value == 0:
            # Take at least one item with positive value
            for i in items:
                if self.values[i] > 0:
                    offer[i] = self.counts[i]
                    break
        
        return offer
    
    def _make_counter_offer(self) -> list[int]:
        """Create counter-offer after receiving opponent's offer"""
        # Calculate target value based on remaining rounds
        if self.rounds_remaining <= 2:
            target_ratio = 0.35
        elif self.rounds_remaining <= 5:
            target_ratio = 0.45
        elif self.rounds_remaining <= 10:
            target_ratio = 0.5
        else:
            target_ratio = 0.55
            
        target_value = int(self.total_value * target_ratio)
        offer = [0] * len(self.counts)
        
        # Sort items by comparative advantage (our value vs opponent value)
        items = list(range(len(self.counts)))
        opp_vals = self.opponent_valuations if self.opponent_valuations else [1] * len(self.counts)
        
        def comparative_advantage(i):
            our_val = self.values[i]
            opp_val = opp_vals[i]
            if opp_val == 0:
                return float('inf') if our_val > 0 else 0
            return our_val / opp_val
        
        items.sort(key=comparative_advantage, reverse=True)
        
        # Allocate items to reach target
        current_value = 0
        for i in items:
            if current_value >= target_value and self.values[i] > 0:
                # Try to add just this item
                item_value = self.counts[i] * self.values[i]
                if current_value + item_value <= self.total_value and current_value + item_value <= target_value * 1.1:
                    offer[i] = self.counts[i]
                    current_value += item_value
                break
                
            offer[i] = self.counts[i]
            current_value += self.counts[i] * self.values[i]
            
        # Ensure we don't end up with zero value if we can avoid it
        if current_value == 0:
            # Take items with highest comparative advantage
            for i in items:
                if self.values[i] > 0:
                    offer[i] = self.counts[i]
                    break
        
        return offer