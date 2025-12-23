class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        
        # If responding to an offer
        if o is not None:
            offer_value = sum(o_i * v_i for o_i, v_i in zip(o, self.values))
            
            # Acceptance logic based on how close we are to deadline
            turns_remaining = total_turns - self.turn_count
            if turns_remaining == 0:
                # Final turn - accept anything better than 0
                if offer_value > 0:
                    return None
            elif turns_remaining <= 2:
                # Last few turns - accept if we get at least 45% of total value
                if offer_value >= self.total_value * 0.45:
                    return None
            elif turns_remaining <= 5:
                # Medium late game - accept if we get at least 50% of total value  
                if offer_value >= self.total_value * 0.5:
                    return None
            else:
                # Early game - only accept if we get 60% or more
                if offer_value >= self.total_value * 0.6:
                    return None
        
        # Generate our offer - take valuable items first
        offer = [0] * len(self.counts)
        
        # Calculate how much we should aim for based on remaining turns
        turns_remaining = total_turns - self.turn_count
        if turns_remaining == 0:
            # Final offer - be very reasonable (just over 50%)
            target_value = self.total_value * 0.51
        elif turns_remaining <= 2:
            # Last few offers - aim for 60%
            target_value = self.total_value * 0.6
        elif turns_remaining <= 5:
            # Medium late game - aim for 65%
            target_value = self.total_value * 0.65
        else:
            # Early game - aim for 75-80%
            target_value = self.total_value * 0.75
        
        # Fill offer with most valuable items first
        current_value = 0
        # Get indices sorted by our value (descending)
        valuable_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        for i in valuable_indices:
            if self.values[i] == 0:
                continue
            if current_value >= target_value:
                break
            # Take as many as needed to reach target_value
            remaining_needed = target_value - current_value
            items_to_take = min(self.counts[i], int((remaining_needed + self.values[i] - 1) // self.values[i]))
            offer[i] = items_to_take
            current_value += items_to_take * self.values[i]
        
        # Ensure we don't exceed counts
        for i in range(len(offer)):
            offer[i] = min(offer[i], self.counts[i])
        
        return offer