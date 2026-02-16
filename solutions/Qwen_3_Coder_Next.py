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
        # Update rounds remaining based on whose turn it is
        if o is not None:
            self.rounds_remaining -= 1
        
        # Record opponent's offer if provided
        if o is not None:
            self.offer_history.append(o.copy())
        
        # Estimate opponent valuations from history
        self._update_opponent_valuations()
        
        # If it's our first turn (o is None), make initial offer
        if o is None:
            return self._make_initial_offer()
        
        # Calculate our value for the opponent's offer
        our_value = sum(v * x for v, x in zip(self.values, o))
        
        # Determine if we should accept
        min_acceptable = self._get_min_acceptable_value()
        if our_value >= min_acceptable:
            return None  # Accept
        
        # Make counter-offer
        return self._make_counter_offer()
    
    def _update_opponent_valuations(self):
        """Simple opponent valuation estimation based on their offers"""
        if not self.offer_history:
            return
            
        n_items = len(self.counts)
        self.opponent_valuations = [1] * n_items
        
        # Count how many times opponent kept each item vs gave to us
        total_offers = len(self.offer_history)
        kept_counts = [0] * n_items
        
        for offer in self.offer_history:
            for i in range(n_items):
                # Opponent kept what we didn't get
                kept = self.counts[i] - offer[i]
                kept_counts[i] += kept
        
        # Estimate valuations
        for i in range(n_items):
            if kept_counts[i] == total_offers * self.counts[i]:
                # Opponent always kept this item - likely valuable to them
                self.opponent_valuations[i] = max(1, (self.total_value // n_items) // 2 + 1)
            elif kept_counts[i] == 0:
                # Opponent never kept this item - likely low value to them
                self.opponent_valuations[i] = 1
            else:
                # Mixed behavior - proportional estimation
                ratio = kept_counts[i] / (total_offers * self.counts[i])
                if ratio > 0.7:
                    self.opponent_valuations[i] = max(2, self.values[i] // 2 + 1)
                elif ratio > 0.3:
                    self.opponent_valuations[i] = max(1, self.values[i] // 3 + 1)
                else:
                    self.opponent_valuations[i] = 1
    
    def _get_min_acceptable_value(self) -> int:
        """Calculate minimum acceptable value based on remaining rounds"""
        if self.rounds_remaining <= 1:
            return max(1, int(self.total_value * 0.35))
        elif self.rounds_remaining <= 3:
            return max(1, int(self.total_value * 0.45))
        elif self.rounds_remaining <= 5:
            return max(1, int(self.total_value * 0.5))
        elif self.rounds_remaining <= 8:
            return max(1, int(self.total_value * 0.55))
        else:
            return max(1, int(self.total_value * 0.6))
    
    def _make_initial_offer(self) -> list[int]:
        """Create initial offer (we get first turn)"""
        # Calculate target value based on first-mover advantage
        if self.is_first:
            target_ratio = 0.65
        else:
            target_ratio = 0.55
            
        target = int(self.total_value * target_ratio)
        offer = [0] * len(self.counts)
        
        # Get opponent valuations if not already estimated
        if self.opponent_valuations is None:
            self._update_opponent_valuations()
            
        # Calculate value-to-cost ratio for each item type
        items = list(range(len(self.counts)))
        
        def comparative_advantage(i):
            if self.opponent_valuations:
                opp_val = self.opponent_valuations[i]
            else:
                opp_val = 1
            our_val = self.values[i]
            # We want items we value highly but opponent values less
            if opp_val == 0:
                return float('inf') if our_val > 0 else 0
            return our_val / opp_val
        
        # Sort items by comparative advantage (descending)
        items.sort(key=comparative_advantage, reverse=True)
        
        # Allocate items to reach target
        current_value = 0
        for i in items:
            if current_value >= target and self.values[i] > 0:
                break
                
            offer[i] = self.counts[i]
            current_value += self.counts[i] * self.values[i]
            
        return offer
    
    def _make_counter_offer(self) -> list[int]:
        """Create counter-offer after receiving opponent's offer"""
        # Calculate target value
        target = max(1, int(self.total_value * 0.5))
        offer = [0] * len(self.counts)
        
        # Get opponent valuations if not already estimated
        if self.opponent_valuations is None:
            self._update_opponent_valuations()
            
        # Calculate comparative advantage
        items = list(range(len(self.counts)))
        
        def comparative_advantage(i):
            if self.opponent_valuations:
                opp_val = self.opponent_valuations[i]
            else:
                opp_val = 1
            our_val = self.values[i]
            if opp_val == 0:
                return float('inf') if our_val > 0 else 0
            return our_val / opp_val
        
        # Sort items by comparative advantage (descending)
        items.sort(key=comparative_advantage, reverse=True)
        
        # Allocate items to reach target
        current_value = 0
        for i in items:
            if current_value >= target and self.values[i] > 0:
                break
                
            offer[i] = self.counts[i]
            current_value += self.counts[i] * self.values[i]
            
        return offer