class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.current_turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Sort items by value density (value to us)
        self.indices = sorted(range(len(counts)), key=lambda i: values[i], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_turn += 1
        
        if o is not None:
            # Value of the partner's offer to us
            received_val = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance thresholds based on time remaining
            turns_left = self.total_turns - self.current_turn
            
            # If it's the absolute last turn or second to last, 
            # we must be very pragmatic to avoid 0 profit.
            if turns_left <= 0:
                return None if received_val > 0 else self._create_counter_offer()
            
            # Acceptance Logic:
            # Gemini 2.5 Flash is highly competitive (often offering nothing).
            # We must demand a fair share but lower thresholds as the deadline approaches.
            if turns_left == 1:
                threshold = self.total_value * 0.4
            elif turns_left <= 4:
                threshold = self.total_value * 0.6
            elif turns_left <= 10:
                threshold = self.total_value * 0.75
            else:
                threshold = self.total_value * 0.9
            
            if received_val >= threshold and received_val > 0:
                return None

        # Counter-offer logic
        return self._create_counter_offer()

    def _create_counter_offer(self) -> list[int]:
        # Calculate progress differently to ensure we don't get stuck in a loop
        progress = self.current_turn / self.total_turns
        
        # Target valuation decreases as time runs out
        if progress < 0.3:
            target_ratio = 1.0
        elif progress < 0.6:
            target_ratio = 0.8
        elif progress < 0.85:
            target_ratio = 0.6
        else:
            target_ratio = 0.5
            
        target_val = self.total_value * target_ratio
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Greedy selection of best items for us
        for i in self.indices:
            # If our value for item is 0, give it to the opponent (don't include in my_offer)
            if self.values[i] == 0:
                continue
            
            for _ in range(self.counts[i]):
                if current_val + self.values[i] <= target_val:
                    my_offer[i] += 1
                    current_val += self.values[i]
                else:
                    # Always take at least one high value item if possible
                    if current_val == 0:
                        my_offer[i] += 1
                        current_val += self.values[i]
                    break
        
        # Signal flexibility: If we are asking for almost everything, 
        # drop one item of the lowest non-zero value to us (likely valuable to them).
        if sum(my_offer[i] * self.values[i] for i in range(len(my_offer))) >= self.total_value * 0.9:
            for i in reversed(self.indices):
                if my_offer[i] > 0:
                    my_offer[i] -= 1
                    break

        # Final turn edge case: ensure we aren't returning an empty offer
        if sum(my_offer) == 0:
            my_offer[self.indices[0]] = 1
            
        self.current_turn += 1 
        return my_offer