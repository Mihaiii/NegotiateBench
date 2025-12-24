class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        # Total value of all items to me
        self.total_value = sum(counts[i] * values[i] for i in range(self.n))
        # Total number of turns (2 per round)
        self.total_moves = max_rounds * 2
        self.moves_left = self.total_moves
        
        # Sort item indices by my value in descending order
        self.sorted_indices = sorted(range(self.n), key=lambda i: values[i], reverse=True)
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        """
        Called when it's my turn to act.
        o: The offer from the partner (what they give to me), or None if it's my opening.
        Returns: None to accept, or a list representing what I want for myself.
        """
        self.moves_left -= 1
        progress = 1 - (self.moves_left / self.total_moves)
        
        # If I received an offer, evaluate it
        if o is not None:
            offered_value = sum(o[i] * self.values[i] for i in range(self.n))
            
            # Acceptance Threshold:
            # Starts at 50% and gradually decreases to 40% as time runs out
            min_acceptable = self.total_value * (0.5 - 0.1 * progress)
            
            # If the offer is good enough, ACCEPT
            if offered_value >= min_acceptable:
                return None
            
            # Special case: Last resort on the final turn. 
            # If I reject now and make an offer, the partner might reject and we get 0.
            # So if this is my last possible turn (moves_left == 1) and offer > 0, accept.
            # Note: moves_left == 1 means this is my last turn.
            # If I am second player, my last turn is when moves_left == 1.
            # If I am first player, my last turn is when moves_left == 1.
            # Actually, if moves_left == 1, it's my turn. After I play, moves_left becomes 0.
            # Partner plays last.
            # If I return an offer on my last turn, partner decides.
            # If I return None, deal is done.
            # So yes, if moves_left == 1 and offer is reasonable, accept.
            if self.moves_left == 1 and offered_value > 0:
                return None

        # If I reach here, I am making a counter-offer (or opening)
        
        # My Target Value:
        # I aim for ~55% initially and concede to ~50% at the very end.
        # This creates a bargaining zone where I ask for more than 50% 
        # but accept down to 40-50%.
        target = self.total_value * (0.55 - 0.05 * progress)
        
        # Build the offer
        return self._build_counter_offer(target)

    def _build_counter_offer(self, target_value: float) -> list[int]:
        """
        Constructs a counter-offer that gives me at least 'target_value'.
        Uses a greedy algorithm prioritizing highest value items.
        """
        offer = [0] * self.n
        remaining = self.counts[:]
        current_value = 0
        
        # First pass: Take the highest value items one by one
        for i in self.sorted_indices:
            if remaining[i] > 0:
                take = min(remaining[i], 1)
                offer[i] = take
                remaining[i] -= take
                current_value += take * self.values[i]
                
        # Second pass: If we haven't reached the target, take more of the remaining items
        # (preferring high value, but we might need to take multiple of a type)
        if current_value < target_value:
            for i in self.sorted_indices:
                while remaining[i] > 0 and current_value < target_value:
                    # Take one more of this item
                    offer[i] += 1
                    remaining[i] -= 1
                    current_value += self.values[i]
        
        # Final adjustment: Ensure we offer a valid partition.
        # The partner gets 'counts - offer'.
        return offer