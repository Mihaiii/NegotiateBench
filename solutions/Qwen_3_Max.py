class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.current_round = 0
        
        # Calculate total value for self
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Generate all possible allocations (what I get) - but only if feasible
        # Since the state space might be large, we'll use a greedy approach instead
        # We'll focus on high-value items first
        
    def _calculate_value(self, allocation: list[int]) -> int:
        """Calculate the value of an allocation to self."""
        return sum(a * v for a, v in zip(allocation, self.values))
    
    def _is_valid_allocation(self, allocation: list[int]) -> bool:
        """Check if allocation is valid (non-negative and doesn't exceed counts)."""
        return all(0 <= a <= c for a, c in zip(allocation, self.counts))
    
    def _get_greedy_demand(self, min_value: int) -> list[int]:
        """Get a greedy allocation that achieves at least min_value."""
        # Start with nothing
        allocation = [0] * len(self.counts)
        current_value = 0
        
        # Create list of (value_per_item, item_index) for items with positive value
        valuable_items = [(self.values[i], i) for i in range(len(self.values)) if self.values[i] > 0]
        # Sort by value descending (greedy: take highest value items first)
        valuable_items.sort(reverse=True)
        
        # Try to add items starting from highest value
        for value_per_item, item_idx in valuable_items:
            if current_value >= min_value:
                break
            # Add as many as needed/available
            needed_value = min_value - current_value
            needed_items = (needed_value + value_per_item - 1) // value_per_item  # ceiling division
            can_take = min(needed_items, self.counts[item_idx])
            allocation[item_idx] = can_take
            current_value += can_take * value_per_item
        
        # If we still haven't reached min_value, take everything valuable
        if current_value < min_value:
            for i, value in enumerate(self.values):
                if value > 0:
                    allocation[i] = self.counts[i]
        
        return allocation
    
    def _get_conservative_offer(self) -> list[int]:
        """Get a more reasonable offer that leaves something for the opponent."""
        allocation = [0] * len(self.counts)
        
        # Take all items that are worthless to me (give them to opponent)
        # Take only what I need to get a good deal
        valuable_items = [(self.values[i], i) for i in range(len(self.values)) if self.values[i] > 0]
        valuable_items.sort(reverse=True)
        
        # Calculate target value based on remaining rounds
        rounds_remaining = self.max_rounds - self.current_round
        if rounds_remaining <= 1:
            # Last round, be more aggressive
            target_value = self.total_value * 0.7
        elif rounds_remaining <= 2:
            target_value = self.total_value * 0.6
        else:
            target_value = self.total_value * 0.55
        
        current_value = 0
        for value_per_item, item_idx in valuable_items:
            if current_value >= target_value:
                break
            # Take most of the items but leave some for opponent to make deal acceptable
            available = self.counts[item_idx]
            if available <= 2:
                take = available  # if few items, take all
            else:
                take = max(1, available - 1)  # leave at least 1 if possible
            allocation[item_idx] = take
            current_value += take * value_per_item
        
        return allocation
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_round += 1
        rounds_remaining = self.max_rounds - self.current_round + 1
        
        # If this is a counter-offer from opponent
        if o is not None:
            # Check if we should accept
            offer_value = self._calculate_value(o)
            
            # Determine minimum acceptable value based on rounds remaining
            if rounds_remaining <= 1:  # This is the last chance to accept
                min_acceptable = self.total_value * 0.4
            elif rounds_remaining <= 2:
                min_acceptable = self.total_value * 0.45
            else:
                min_acceptable = self.total_value * 0.5
            
            if offer_value >= min_acceptable:
                return None  # Accept the offer
        
        # Make a counter-offer
        if rounds_remaining <= 1:
            # Last round - be aggressive, demand high value
            return self._get_greedy_demand(int(self.total_value * 0.7))
        elif rounds_remaining <= 2:
            # Second to last round - still somewhat aggressive
            return self._get_greedy_demand(int(self.total_value * 0.6))
        else:
            # Early rounds - be more reasonable to encourage agreement
            return self._get_conservative_offer()