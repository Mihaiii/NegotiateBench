class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        
    def _calculate_value(self, allocation: list[int]) -> int:
        """Calculate the value of an allocation to self."""
        return sum(a * v for a, v in zip(allocation, self.values))
    
    def _is_valid_allocation(self, allocation: list[int]) -> bool:
        """Check if allocation is valid."""
        return all(0 <= a <= c for a, c in zip(allocation, self.counts))
    
    def _get_greedy_offer(self, keep_fraction: float) -> list[int]:
        """Get offer by taking high-value items, keeping fraction of total value."""
        # Create list of items sorted by our value per item (descending)
        items = [(self.values[i], i) for i in range(len(self.values))]
        items.sort(reverse=True)
        
        allocation = [0] * len(self.counts)
        target_value = self.total_value * keep_fraction
        current_value = 0
        
        for value_per_item, idx in items:
            if value_per_item == 0:
                # We don't value this item, so don't take any
                allocation[idx] = 0
                continue
                
            if current_value >= target_value:
                # We've reached our target, don't take more
                allocation[idx] = 0
                continue
                
            # Take as many as we can of this valuable item
            remaining_needed = target_value - current_value
            max_items_needed = (remaining_needed + value_per_item - 1) // value_per_item
            take = min(max_items_needed, self.counts[idx])
            allocation[idx] = take
            current_value += take * value_per_item
            
        return allocation
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn_count
        
        # If opponent made an offer, consider accepting it
        if o is not None:
            offer_value = self._calculate_value(o)
            # Calculate acceptance threshold based on turns remaining
            if turns_remaining == 0:
                # This shouldn't happen, but be safe
                threshold = 0.0
            elif turns_remaining <= 2:
                # Very few turns left, accept lower offers
                threshold = 0.3
            elif turns_remaining <= 4:
                # Few turns left, be more flexible
                threshold = 0.4
            else:
                # Plenty of time, hold out for better deals
                threshold = 0.5
                
            if offer_value >= threshold * self.total_value:
                return None  # Accept the offer
        
        # Determine how much value to aim for in our counter-offer
        progress = self.turn_count / total_turns
        if progress < 0.3:
            # Early game: aim high (70-80% of our total value)
            keep_fraction = 0.75
        elif progress < 0.6:
            # Mid game: moderate demands (60-70%)
            keep_fraction = 0.65
        elif progress < 0.8:
            # Late game: be more reasonable (50-60%)
            keep_fraction = 0.55
        else:
            # Very late game: ensure we get something (40-50%)
            keep_fraction = 0.45
            
        # Make sure we don't go below 30% even in desperation
        keep_fraction = max(keep_fraction, 0.3)
        
        # Generate our offer
        offer = self._get_greedy_offer(keep_fraction)
        
        # Safety check: ensure offer is valid
        if not self._is_valid_allocation(offer):
            # Fallback: take all items we value
            offer = [self.counts[i] if self.values[i] > 0 else 0 for i in range(len(self.counts))]
            
        # Additional safety: if our offer value is too low, try to improve it
        offer_value = self._calculate_value(offer)
        if offer_value < 0.3 * self.total_value:
            # Try to get at least 30% by taking more valuable items
            offer = self._get_greedy_offer(0.3)
            
        return offer