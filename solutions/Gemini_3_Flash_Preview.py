class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.current_turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        # Items sorted by value to us (highest first)
        self.pref_indices = sorted(range(len(counts)), key=lambda i: values[i], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Update turn counter
        if o is None:
            self.current_turn = 0
        else:
            # We assume alternating steps. If we are 1, we receive turn 0, 2, 4...
            # If we are 0, we receive turn 1, 3, 5...
            self.current_turn += 2 if self.current_turn > 0 or self.me == 0 else 1

        turns_remaining = self.total_turns - self.current_turn
        progress = self.current_turn / self.total_turns

        # Valuation of the offer provided to us
        offer_val = 0
        if o is not None:
            offer_val = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance Strategy
            # Very early: only 95%+
            # Mid: 75%
            # Late: 60%
            # End: Above 50% or any value if it's the final turn to avoid 0.
            if progress < 0.2:
                threshold = 0.9 * self.total_value
            elif progress < 0.6:
                threshold = 0.75 * self.total_value
            elif progress < 0.9:
                threshold = 0.6 * self.total_value
            else:
                threshold = 0.5 * self.total_value

            # If it's the very last turn (our partner's turn was the last chance to offer)
            # and we are player 1, this 'o' is the final proposal.
            if turns_remaining <= 1:
                if offer_val > 0:
                    return None
            
            if offer_val >= max(threshold, 1):
                return None

        # Counter-offer Strategy
        # Concede target value over time
        if progress < 0.25:
            target_ratio = 1.0
        elif progress < 0.5:
            target_ratio = 0.9
        elif progress < 0.75:
            target_ratio = 0.8
        elif progress < 0.9:
            target_ratio = 0.7
        else:
            target_ratio = 0.6

        return self._build_offer(target_ratio)

    def _build_offer(self, ratio: float) -> list[int]:
        target_val = ratio * self.total_value
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Greedy allocation based on our preferences
        for i in self.pref_indices:
            for _ in range(self.counts[i]):
                if current_val + self.values[i] <= target_val or current_val == 0:
                    my_offer[i] += 1
                    current_val += self.values[i]
                else:
                    break
        
        # Ensure we don't demand everything if we want to encourage an agreement, 
        # especially in the second half of the game.
        if sum(my_offer) == sum(self.counts) and self.total_value > 0:
            # Drop the item least valuable to us
            for i in reversed(self.pref_indices):
                if my_offer[i] > 0:
                    my_offer[i] -= 1
                    break

        # Safety: If result gives us 0 value but we have value-items, take the smallest one.
        if sum(m * v for m, v in zip(my_offer, self.values)) == 0 and self.total_value > 0:
            for i in reversed(self.pref_indices):
                if self.values[i] > 0:
                    my_offer[i] = 1
                    break
            
        return my_offer