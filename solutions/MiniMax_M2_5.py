class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.me = me
        self.turn = 0
        self.total = sum(c * v for c, v in zip(counts, values))
        self.best_received = None
        self.opponent_values_estimate = None
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        current_round = (self.turn + 1) // 2
        remaining_rounds = self.max_rounds - current_round + 1
        
        # Track best offer received
        if o is not None:
            my_value = sum(o[i] * self.values[i] for i in range(len(o)))
            if self.best_received is None or my_value > sum(self.best_received[i] * self.values[i] for i in range(len(self.best_received))):
                self.best_received = o
        
        # ACCEPTANCE STRATEGY
        if o is not None:
            my_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Calculate minimum acceptable - be more flexible as rounds decrease
            # Start at ~42%, decrease to ~35% by end
            min_acceptable = self.total * (0.42 - 0.07 * (current_round - 1) / max(1, self.max_rounds - 1))
            
            # Accept if offer meets our minimum threshold
            if my_value >= min_acceptable:
                return None
            
            # In final rounds, accept any decent offer
            if remaining_rounds <= 2 and my_value >= self.total * 0.35:
                return None
            
            # If it's the last turn and we haven't accepted, we must make an offer
            if remaining_rounds == 1 and self.best_received is not None:
                # Accept best offer if current one is not better
                best_val = sum(self.best_received[i] * self.values[i] for i in range(len(self.best_received)))
                if my_value < best_val:
                    return None
        
        # OFFER STRATEGY
        # Calculate target value - start higher, concede as we progress
        initial_target = 0.52
        final_target = 0.38
        progress = (current_round - 1) / max(1, self.max_rounds - 1)
        target_pct = initial_target - progress * (initial_target - final_target)
        target_value = self.total * target_pct
        
        # Build offer: start with all items, remove strategically
        offer = self.counts.copy()
        
        # Items we value least should be offered to opponent first
        # Sort by value (ascending) - remove cheapest items first
        items_by_value = sorted([(self.values[i], i) for i in range(len(self.counts))])
        
        current_value = self.total
        for value, i in items_by_value:
            while offer[i] > 0 and current_value > target_value:
                offer[i] -= 1
                current_value -= value
        
        # Ensure valid allocation
        if sum(offer) != sum(self.counts):
            # Give opponent any remaining items
            for i in range(len(offer)):
                if offer[i] < self.counts[i]:
                    offer[i] = self.counts[i]
            # Re-adjust by removing from lowest value items
            current_value = sum(offer[i] * self.values[i] for i in range(len(offer)))
            for value, i in items_by_value:
                while offer[i] > 0 and current_value > target_value:
                    offer[i] -= 1
                    current_value -= value
        
        return offer