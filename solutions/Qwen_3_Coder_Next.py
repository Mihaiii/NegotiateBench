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
        
        # Calculate opponent's value for their offer
        opponent_value = self._calculate_opponent_value(o)
        
        # Determine if we should accept
        if self._should_accept(our_value, opponent_value):
            return None  # Accept
        
        # Make counter-offer
        return self._make_counter_offer()
    
    def _update_opponent_valuations(self):
        """Estimate opponent valuations based on their past offers"""
        if not self.offer_history:
            # Default estimate: if we don't know, assume opponent values items differently
            n_items = len(self.counts)
            self.opponent_valuations = [max(1, (self.total_value // n_items) // 2) for _ in range(n_items)]
            return
            
        n_items = len(self.counts)
        self.opponent_valuations = [1] * n_items
        
        # Count how many times opponent kept each item vs gave to us across all offers
        total_offers = len(self.offer_history)
        kept_counts = [0] * n_items
        total_kept_counts = [0] * n_items
        
        for offer in self.offer_history:
            for i in range(n_items):
                # Opponent kept what we didn't get
                kept = self.counts[i] - offer[i]
                kept_counts[i] += kept
                total_kept_counts[i] += self.counts[i]
        
        # Estimate valuations based on how much opponent kept each item
        for i in range(n_items):
            if total_kept_counts[i] == 0:
                self.opponent_valuations[i] = 1
                continue
                
            ratio = kept_counts[i] / total_kept_counts[i]
            
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
                self.opponent_valuations[i] = max(1, (self.total_value // n_items) // 3)
    
    def _calculate_opponent_value(self, offer: list[int]) -> int:
        """Estimate opponent's value for an offer from our perspective (what we get)"""
        if not self.opponent_valuations:
            return 0
            
        # Opponent gets what we don't get
        opponent_gets = [self.counts[i] - offer[i] for i in range(len(self.counts))]
        return sum(v * x for v, x in zip(self.opponent_valuations, opponent_gets))
    
    def _should_accept(self, our_value: int, opponent_value: int) -> bool:
        """Determine if we should accept the current offer"""
        # If we're out of rounds, accept almost anything
        if self.rounds_remaining <= 1:
            # In final round, accept any offer with positive value
            return our_value > 0
            
        # If opponent seems very satisfied (they got most value), accept a bit less
        if opponent_value > self.total_value * 0.75 and our_value >= self.total_value * 0.3:
            return True
            
        # Calculate minimum acceptable value based on remaining rounds
        if self.rounds_remaining <= 3:
            min_acceptable = max(1, int(self.total_value * 0.35))
        elif self.rounds_remaining <= 5:
            min_acceptable = max(1, int(self.total_value * 0.45))
        elif self.rounds_remaining <= 8:
            min_acceptable = max(1, int(self.total_value * 0.5))
        elif self.rounds_remaining <= 12:
            min_acceptable = max(1, int(self.total_value * 0.55))
        else:
            min_acceptable = max(1, int(self.total_value * 0.6))
        
        # Adjust based on whether opponent seems flexible
        if self.opponent_valuations:
            # If opponent's valuation estimate seems low for items they kept, they might accept less
            # This is a heuristic - adjust acceptance threshold if opponent appears flexible
            if opponent_value > self.total_value * 0.7 and our_value >= min_acceptable * 0.8:
                return True
        
        return our_value >= min_acceptable
    
    def _make_initial_offer(self) -> list[int]:
        """Create initial offer (we get first turn)"""
        offer = [0] * len(self.counts)
        
        # Calculate how much value we want to keep for ourselves
        if self.is_first:
            target_ratio = 0.6  # First mover advantage - aim for 60%
        else:
            target_ratio = 0.55
            
        target_value = int(self.total_value * target_ratio)
        
        # Sort items by our value to opponent value ratio (descending)
        items = list(range(len(self.counts)))
        items.sort(key=lambda i: self.values[i] / max(1, self.opponent_valuations[i] if self.opponent_valuations else 1), reverse=True)
        
        # Allocate items to reach target value
        current_value = 0
        for i in items:
            if current_value >= target_value and self.values[i] > 0:
                # Try to add just this item to see if we can get closer to target
                item_value = self.counts[i] * self.values[i]
                if current_value + item_value <= self.total_value and current_value + item_value <= target_value * 1.1:
                    offer[i] = self.counts[i]
                    current_value += item_value
                break
                
            offer[i] = self.counts[i]
            current_value += self.counts[i] * self.values[i]
            
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
        
        def comparative_advantage(i):
            our_val = self.values[i]
            opp_val = self.opponent_valuations[i] if self.opponent_valuations else 1
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
            
        return offer