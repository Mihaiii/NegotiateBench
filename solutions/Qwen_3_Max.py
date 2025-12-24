class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.opponent_offers = []
        self.opponent_valuation_guess = [1] * len(values)  # Initial uniform guess
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn_count
        
        # Handle incoming offer
        if o is not None:
            self.opponent_offers.append(o)
            offer_value = sum(o_i * v_i for o_i, v_i in zip(o, self.values))
            
            # Update opponent valuation guess based on their offers
            self._update_opponent_valuation_guess(o)
            
            # Accept if offer is good enough
            min_acceptable = self._get_min_acceptable_value(turns_remaining)
            if offer_value >= min_acceptable:
                return None
        
        # Create our counter-offer
        return self._create_counter_offer(turns_remaining)
    
    def _update_opponent_valuation_guess(self, offer: list[int]):
        """Update our guess of opponent's valuations based on what they offer us."""
        # If opponent offers us few of an item, they probably value it highly
        # If they offer us many of an item, they probably value it less
        for i in range(len(self.counts)):
            if self.counts[i] > 0:
                # What opponent keeps for themselves
                opponent_keeps = self.counts[i] - offer[i]
                # Higher opponent_keeps suggests higher opponent value
                # Normalize to create relative valuation
                ratio = opponent_keeps / self.counts[i] if self.counts[i] > 0 else 0
                # Update with some smoothing
                self.opponent_valuation_guess[i] = 0.7 * self.opponent_valuation_guess[i] + 0.3 * ratio
    
    def _get_min_acceptable_value(self, turns_remaining: int) -> float:
        """Determine minimum value we should accept based on remaining turns."""
        if turns_remaining <= 1:
            return max(1, self.total_value * 0.2)  # Accept almost anything in final turn
        elif turns_remaining <= 3:
            return self.total_value * 0.4
        elif turns_remaining <= 6:
            return self.total_value * 0.5
        else:
            return self.total_value * 0.55  # Be reasonable from the start
    
    def _create_counter_offer(self, turns_remaining: int) -> list[int]:
        """Create a counter-offer that balances our value with opponent's likely preferences."""
        # Determine our target value based on remaining turns
        if turns_remaining <= 2:
            target_value = self.total_value * 0.5
        elif turns_remaining <= 6:
            target_value = self.total_value * 0.6
        else:
            target_value = self.total_value * 0.65
        
        # Create list of items with our value and guessed opponent value
        item_info = []
        for i in range(len(self.values)):
            if self.values[i] > 0:
                item_info.append((i, self.values[i], self.opponent_valuation_guess[i]))
        
        # Sort by ratio of our value to opponent's guessed value (descending)
        # This prioritizes items that are valuable to us but less valuable to opponent
        item_info.sort(key=lambda x: x[1] / (x[2] + 0.1), reverse=True)
        
        # Build offer by taking items in priority order until we reach target
        offer = [0] * len(self.counts)
        current_value = 0
        
        for idx, our_val, opp_val in item_info:
            if current_value >= target_value:
                break
            # Take as many as needed to reach target, but be reasonable
            needed_value = target_value - current_value
            max_items_to_take = min(self.counts[idx], (needed_value + our_val - 1) // our_val)
            # Don't take everything if opponent seems to value it highly
            if opp_val > 0.7:  # Opponent likely values this highly
                max_items_to_take = min(max_items_to_take, max(0, self.counts[idx] - 1))
            offer[idx] = int(max_items_to_take)
            current_value += offer[idx] * our_val
        
        # Ensure we don't offer nothing if we have valuable items
        if current_value == 0 and self.total_value > 0:
            # Take the most valuable item we can
            best_idx = max(range(len(self.values)), key=lambda i: self.values[i])
            if self.values[best_idx] > 0:
                offer[best_idx] = min(1, self.counts[best_idx])
        
        # Make sure offer is valid
        for i in range(len(offer)):
            offer[i] = max(0, min(offer[i], self.counts[i]))
        
        return offer