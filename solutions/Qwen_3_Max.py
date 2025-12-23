class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.my_last_offer = None
        self.opponent_last_offer = None
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn_count
        
        # If responding to an offer
        if o is not None:
            self.opponent_last_offer = o
            offer_value = sum(o_i * v_i for o_i, v_i in zip(o, self.values))
            
            # Acceptance logic - be more flexible as deadline approaches
            if turns_remaining == 0:
                # Final turn - accept anything better than 0
                if offer_value > 0:
                    return None
            elif turns_remaining <= 1:
                # Second to last turn - accept 40% or more
                if offer_value >= self.total_value * 0.4:
                    return None
            elif turns_remaining <= 3:
                # Accept 45% or more in late game
                if offer_value >= self.total_value * 0.45:
                    return None
            elif turns_remaining <= 6:
                # Accept 50% or more in mid game
                if offer_value >= self.total_value * 0.5:
                    return None
            else:
                # Early game - accept 60% or more
                if offer_value >= self.total_value * 0.6:
                    return None
        
        # Generate our offer based on remaining turns and opponent behavior
        if turns_remaining == 0:
            # Final offer - be very reasonable (just over 50%)
            target_share = 0.51
        elif turns_remaining <= 2:
            # Last few offers - aim for 55-60%
            target_share = 0.55
        elif turns_remaining <= 5:
            # Medium late game - aim for 60-65%
            target_share = 0.62
        else:
            # Early game - aim for 70-75%
            target_share = 0.72
        
        target_value = self.total_value * target_share
        
        # Create offer by taking valuable items, but be reasonable
        offer = [0] * len(self.counts)
        current_value = 0
        
        # Sort items by our value (descending)
        valuable_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        for i in valuable_indices:
            if self.values[i] == 0:
                continue
            # Take items but don't be greedy - leave some room for opponent
            max_take = self.counts[i]
            if self.turn_count > 1 and self.opponent_last_offer is not None:
                # If opponent has been conceding on this item, we can take more
                # But if they're holding firm, be more conservative
                opponent_wants = self.counts[i] - self.opponent_last_offer[i]
                if opponent_wants > 0 and self.values[i] > 0:
                    # They want this item too - be more conservative
                    max_take = min(max_take, max(0, self.counts[i] // 2 + 1))
            
            # Calculate how many we actually need
            remaining_needed = target_value - current_value
            if remaining_needed <= 0:
                break
                
            items_to_take = min(max_take, int((remaining_needed + self.values[i] - 1) // self.values[i]))
            items_to_take = min(items_to_take, self.counts[i])
            offer[i] = items_to_take
            current_value += items_to_take * self.values[i]
        
        # Ensure we don't exceed counts
        for i in range(len(offer)):
            offer[i] = min(offer[i], self.counts[i])
        
        # Make sure our offer is valid (doesn't exceed available items)
        for i in range(len(offer)):
            if offer[i] > self.counts[i]:
                offer[i] = self.counts[i]
        
        # If we're in late rounds and our previous offer was rejected,
        # make a slightly more generous offer to the opponent
        if self.turn_count > 2 and turns_remaining <= 4 and self.my_last_offer is not None:
            # Calculate current offer value
            current_offer_value = sum(offer[i] * self.values[i] for i in range(len(offer)))
            previous_offer_value = sum(self.my_last_offer[i] * self.values[i] for i in range(len(self.my_last_offer)))
            
            # If we're not already being very generous, concede a bit more
            if current_offer_value > self.total_value * 0.55:
                # Reduce our demand slightly
                reduction_amount = min(current_offer_value - self.total_value * 0.52, 
                                     (current_offer_value - previous_offer_value) * 0.3)
                if reduction_amount > 0:
                    # Remove least valuable items first
                    less_valuable_indices = sorted(range(len(self.values)), key=lambda i: self.values[i])
                    remaining_reduction = reduction_amount
                    new_offer = offer[:]
                    for i in less_valuable_indices:
                        if remaining_reduction <= 0 or new_offer[i] == 0:
                            continue
                        item_value = self.values[i]
                        items_to_remove = min(new_offer[i], int((remaining_reduction + item_value - 1) // item_value))
                        new_offer[i] -= items_to_remove
                        remaining_reduction -= items_to_remove * item_value
                        if remaining_reduction <= 0:
                            break
                    offer = new_offer
        
        self.my_last_offer = offer[:]
        return offer