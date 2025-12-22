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
    
    def _get_my_demand_allocation(self, target_value: int) -> list[int]:
        """Get allocation that achieves target_value by taking highest value items first."""
        allocation = [0] * len(self.counts)
        current_value = 0
        
        # Sort items by value descending
        valuable_items = [(self.values[i], i) for i in range(len(self.values)) if self.values[i] > 0]
        valuable_items.sort(reverse=True)
        
        for value_per_item, item_idx in valuable_items:
            if current_value >= target_value:
                break
            # Take as many as needed
            needed_value = target_value - current_value
            needed_items = (needed_value + value_per_item - 1) // value_per_item
            can_take = min(needed_items, self.counts[item_idx])
            allocation[item_idx] = can_take
            current_value += can_take * value_per_item
        
        # If still not enough, take all valuable items
        if current_value < target_value:
            for i, value in enumerate(self.values):
                if value > 0:
                    allocation[i] = self.counts[i]
                    
        return allocation
    
    def _estimate_opponent_valuation(self) -> list[int]:
        """Estimate opponent's valuations based on their offers."""
        if not self.opponent_offers:
            # No data, assume uniform or inverse correlation
            return [1 if v == 0 else 0 for v in self.values]
        
        # Simple estimation: if opponent consistently offers us few of an item type,
        # they likely value it highly
        estimated_values = [0] * len(self.counts)
        
        for offer in self.opponent_offers:
            for i in range(len(self.counts)):
                # If they offer us few items of type i, they probably want it
                offered_to_us = offer[i]
                total_available = self.counts[i]
                they_keep = total_available - offered_to_us
                # Higher they_keep suggests higher value to them
                estimated_values[i] += they_keep
        
        # Normalize to reasonable range
        if max(estimated_values) > 0:
            max_val = max(estimated_values)
            estimated_values = [int((v / max_val) * 10) if max_val > 0 else 0 for v in estimated_values]
        
        return estimated_values
    
    def _create_reasonable_offer(self, opponent_values: list[int]) -> list[int]:
        """Create an offer that gives opponent items they likely value."""
        allocation = [0] * len(self.counts)
        
        # For each item type, decide how much to take
        for i in range(len(self.counts)):
            my_value = self.values[i]
            opp_value = opponent_values[i]
            
            if my_value == 0 and opp_value > 0:
                # I don't value it, they do - give it all to them
                allocation[i] = 0
            elif my_value > 0 and opp_value == 0:
                # I value it, they don't - take it all
                allocation[i] = self.counts[i]
            elif my_value > 0 and opp_value > 0:
                # Both value it - split reasonably
                if my_value >= opp_value:
                    # I value it more, take majority
                    allocation[i] = self.counts[i]
                else:
                    # They value it more, take minority or none
                    allocation[i] = max(0, self.counts[i] // 2)
            else:
                # Neither values it - take half
                allocation[i] = self.counts[i] // 2
                
        return allocation
    
    def _get_acceptance_threshold(self, rounds_remaining: int) -> float:
        """Determine minimum acceptable value based on rounds remaining."""
        if rounds_remaining == 1:
            # Last chance - accept almost anything
            return 0.3
        elif rounds_remaining <= 2:
            return 0.4
        elif rounds_remaining <= 4:
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
                return None  # Accept
        
        # Make a counter-offer
        opponent_values = self._estimate_opponent_valuation()
        reasonable_offer = self._create_reasonable_offer(opponent_values)
        
        # Ensure our offer has reasonable value to us
        current_value = self._calculate_value(reasonable_offer)
        target_value = self.total_value * self._get_acceptance_threshold(rounds_remaining - 1)
        
        if current_value < target_value:
            # Boost our offer to meet minimum target
            reasonable_offer = self._get_my_demand_allocation(int(target_value))
        
        # Final validation
        if not self._is_valid_allocation(reasonable_offer):
            # Fallback: take all valuable items
            reasonable_offer = [self.counts[i] if self.values[i] > 0 else 0 
                              for i in range(len(self.counts))]
        
        return reasonable_offer