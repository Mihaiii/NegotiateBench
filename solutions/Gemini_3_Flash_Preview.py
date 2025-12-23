class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.current_turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Priority order for items: highest value to us first
        self.indices = sorted(range(len(counts)), key=lambda i: values[i], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_turn += 1
        
        if o is not None:
            # Calculate value of partner's offer to us
            received_val = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance logic: be firm early, lenient late
            # turns_left includes the current decision and potentially one last offer if we are 2nd player
            turns_left = self.total_turns - self.current_turn
            
            if turns_left <= 0:
                # Absolute last chance
                if received_val > 0:
                    return None
            elif turns_left <= 1:
                # Very late: accept anything reasonable (>= 30% or at least 1)
                if received_val >= max(1, self.total_value * 0.3):
                    return None
            elif turns_left <= 4:
                # Late game: accept >= 60%
                if received_val >= self.total_value * 0.6:
                    return None
            else:
                # Early game: only accept high offers >= 85%
                if received_val >= self.total_value * 0.85:
                    return None

        # Counter-offer logic
        return self._create_counter_offer()

    def _create_counter_offer(self) -> list[int]:
        # Determine how much we should demand based on how deep we are in the negotiation
        progress = self.current_turn / self.total_turns
        
        if progress < 0.2:
            target_ratio = 1.0 # Ask for everything
        elif progress < 0.5:
            target_ratio = 0.9 # Slightly concede
        elif progress < 0.8:
            target_ratio = 0.7 # Yield more
        else:
            target_ratio = 0.6 # Minimum comfortable demand

        target_val = self.total_value * target_ratio
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Fill offer with most valuable items first
        for i in self.indices:
            count = self.counts[i]
            val = self.values[i]
            if val == 0:
                continue
            
            for _ in range(count):
                if current_val + val <= target_val or current_val == 0:
                    my_offer[i] += 1
                    current_val += val
                else:
                    break
        
        # Concession: if we're asking for everything, give away the most useless item
        # to signal willingness to negotiate
        if sum(my_offer) == sum(self.counts):
            for i in reversed(self.indices):
                if my_offer[i] > 0:
                    my_offer[i] -= 1
                    break
                    
        # Final safety: Ensure we never return an empty offer if we have values
        if sum(my_offer) == 0 and self.total_value > 0:
            my_offer[self.indices[0]] = 1
            
        self.current_turn += 1 # Increment for our own turn
        return my_offer