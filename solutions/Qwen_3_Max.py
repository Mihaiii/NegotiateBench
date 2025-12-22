class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.round = 0
        self.opponent_offers = []
        
    def _calculate_value(self, allocation: list[int]) -> int:
        """Calculate the value of an allocation to self."""
        return sum(a * v for a, v in zip(allocation, self.values))
    
    def _is_valid_allocation(self, allocation: list[int]) -> bool:
        """Check if allocation is valid."""
        return all(0 <= a <= c for a, c in zip(allocation, self.counts))
    
    def _get_greedy_allocation(self, target_value: int) -> list[int]:
        """Get allocation by taking highest value items first to reach target."""
        allocation = [0] * len(self.counts)
        current_value = 0
        
        # Create list of (value_per_item, index) for items with positive value
        valuable_items = [(self.values[i], i) for i in range(len(self.values)) if self.values[i] > 0]
        valuable_items.sort(reverse=True)  # Highest value first
        
        for value_per_item, item_idx in valuable_items:
            if current_value >= target_value:
                break
            # Take as many as needed of this item
            needed_value = target_value - current_value
            needed_items = (needed_value + value_per_item - 1) // value_per_item
            can_take = min(needed_items, self.counts[item_idx])
            allocation[item_idx] = can_take
            current_value += can_take * value_per_item
            
        return allocation
    
    def _get_conservative_offer(self) -> list[int]:
        """Get a conservative offer that takes only high-value items we care about."""
        allocation = [0] * len(self.counts)
        for i in range(len(self.counts)):
            if self.values[i] > 0:
                allocation[i] = self.counts[i]
        return allocation
    
    def _get_flexible_offer(self, flexibility: float) -> list[int]:
        """Get an offer with some flexibility based on how much we're willing to concede."""
        allocation = [0] * len(self.counts)
        
        # Sort items by our value (descending)
        items = [(self.values[i], i) for i in range(len(self.values))]
        items.sort(reverse=True)
        
        total_needed = int(self.total_value * flexibility)
        current_value = 0
        
        for value, idx in items:
            if value == 0:
                # We don't value this, give it all to opponent
                allocation[idx] = 0
            else:
                # We value this, but be flexible
                if current_value >= total_needed:
                    allocation[idx] = 0
                else:
                    # Take some portion based on flexibility
                    max_take = self.counts[idx]
                    if flexibility >= 0.8:
                        take = max_take
                    elif flexibility >= 0.6:
                        take = max(1, max_take // 2)
                    else:
                        take = min(1, max_take)
                    allocation[idx] = take
                    current_value += take * value
                    
        return allocation
    
    def _get_acceptance_threshold(self, rounds_remaining: int) -> float:
        """Get acceptance threshold based on rounds remaining."""
        if rounds_remaining <= 1:
            return 0.3  # Last round, accept almost anything
        elif rounds_remaining <= 3:
            return 0.4
        elif rounds_remaining <= 6:
            return 0.45
        else:
            return 0.5
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.round += 1
        rounds_remaining = self.max_rounds - self.round + 1
        
        # If opponent made an offer, consider accepting
        if o is not None:
            self.opponent_offers.append(o)
            offer_value = self._calculate_value(o)
            threshold = self._get_acceptance_threshold(rounds_remaining)
            
            if offer_value >= threshold * self.total_value:
                return None  # Accept the offer
        
        # Determine our flexibility based on round progression
        progress = self.round / self.max_rounds
        if progress < 0.3:
            # Early rounds: be greedy
            target_flexibility = 0.8
        elif progress < 0.6:
            # Middle rounds: moderate flexibility
            target_flexibility = 0.6
        else:
            # Late rounds: be more flexible
            target_flexibility = 0.4
            
        # Create our offer
        if rounds_remaining <= 2:
            # Very late game, be extra flexible
            offer = self._get_flexible_offer(0.3)
        else:
            offer = self._get_flexible_offer(target_flexibility)
        
        # Ensure our offer is valid and has reasonable value
        if not self._is_valid_allocation(offer):
            offer = self._get_conservative_offer()
            
        # If our offer has very low value, fall back to greedy allocation
        offer_value = self._calculate_value(offer)
        min_acceptable = self.total_value * 0.3
        if offer_value < min_acceptable:
            offer = self._get_greedy_allocation(int(min_acceptable))
            
        return offer