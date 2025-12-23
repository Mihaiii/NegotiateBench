class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.current_turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        # Sort items by our valuation descending
        self.indices = sorted(range(len(counts)), key=lambda i: values[i], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is not None:
            self.current_turn += 1  # Partner's turn
        
        # Calculate utility of the offer received (o is what we get)
        received_val = sum(o[i] * self.values[i] for i in range(len(o))) if o is not None else 0
        
        # normalized progress (0.0 to 1.0)
        progress = self.current_turn / self.total_turns

        # 1. Decision to Accept
        if o is not None:
            # Stricter at start, more lenient as deadline approaches
            if progress < 0.3:
                threshold = 0.9 * self.total_value
            elif progress < 0.6:
                threshold = 0.75 * self.total_value
            elif progress < 0.85:
                threshold = 0.6 * self.total_value
            else:
                # Last resort: accept if we get something significant, or anything on final turn
                threshold = 0.4 * self.total_value if self.current_turn < self.total_turns - 1 else 1
            
            if received_val >= threshold and received_val > 0:
                return None

        # 2. Counter-offer Logic
        self.current_turn += 1  # Our turn
        
        # Determine target value based on progress
        if progress < 0.2:
            target_ratio = 1.0
        elif progress < 0.5:
            target_ratio = 0.85
        elif progress < 0.8:
            target_ratio = 0.7
        else:
            target_ratio = 0.55

        # If it's the very last turn and we are second player, or nearly last
        if self.current_turn >= self.total_turns - 1:
            # Be ultra-realistic, try to get at least 40% if possible
            target_ratio = 0.4

        return self._build_offer(target_ratio)

    def _build_offer(self, target_ratio: float) -> list[int]:
        target_val = target_ratio * self.total_value
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Step 1: Greedy selection of items starting from most valuable to us
        for i in self.indices:
            if self.values[i] > 0:
                for _ in range(self.counts[i]):
                    if current_val + self.values[i] <= target_val:
                        my_offer[i] += 1
                        current_val += self.values[i]
                    else:
                        break
        
        # Step 2: If we are very far from target due to item granularity, 
        # take at least one high value item if possible.
        if current_val == 0 and self.total_value > 0:
            my_offer[self.indices[0]] = 1
            current_val = self.values[self.indices[0]]

        # Step 3: Concede items that are worthless to us (0 value) 
        # The logic above already left them at 0, which is good.
        # But we must ensure we don't accidentally take them all and look greedy.
        # If we are making a request for almost everything, drop the 0-value items.
        
        # Final safety check: if we are asking for everything and it's not the first turn,
        # concede the smallest possible value item to signal negotiation.
        if sum(my_offer) == sum(self.counts) and self.current_turn > 1:
            for i in reversed(self.indices):
                if my_offer[i] > 0:
                    my_offer[i] -= 1
                    break
                    
        return my_offer