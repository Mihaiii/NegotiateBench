class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.current_turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        # Sort item indices by our valuation descending
        self.indices = sorted(range(len(counts)), key=lambda i: values[i], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_turn += 1 if o is None else 2
        
        # Calculate utility of the offer received (o is what we get)
        received_val = sum(o[i] * self.values[i] for i in range(len(o))) if o is not None else 0
        
        # Time pressure factor (0.0 at start, 1.0 at final turn)
        progress = self.current_turn / self.total_turns

        # 1. Decision to Accept
        if o is not None:
            # Desperation logic for the absolute final turn
            is_final_turn = (self.current_turn >= self.total_turns - 1)
            
            # Acceptance thresholds based on time
            if progress < 0.2:
                threshold = 0.95 * self.total_value
            elif progress < 0.5:
                threshold = 0.8 * self.total_value
            elif progress < 0.8:
                threshold = 0.7 * self.total_value
            elif progress < 0.95:
                threshold = 0.6 * self.total_value
            else:
                # Accept anything better than nothing if it's the very last chance
                threshold = 1 if self.total_value > 0 else 0

            if received_val >= threshold:
                return None

        # 2. Counter-offer Logic
        # We start by demanding most value and slowly concede
        if progress < 0.2:
            target_ratio = 1.0
        elif progress < 0.4:
            target_ratio = 0.9
        elif progress < 0.7:
            target_ratio = 0.8
        elif progress < 0.9:
            target_ratio = 0.7
        else:
            target_ratio = 0.6

        return self._build_offer(target_ratio)

    def _build_offer(self, target_ratio: float) -> list[int]:
        target_val = target_ratio * self.total_value
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Priority 1: Take items that are valuable to us
        for i in self.indices:
            if self.values[i] > 0:
                for _ in range(self.counts[i]):
                    if current_val + self.values[i] <= target_val:
                        my_offer[i] += 1
                        current_val += self.values[i]
                    else:
                        break
        
        # Priority 2: Give away all items that are worthless to us (Zero Value)
        # This signals flexibility to the partner without costing us anything.
        for i in range(len(self.counts)):
            if self.values[i] == 0:
                my_offer[i] = 0
                
        # Safety check: ensure we don't return an empty offer if we have value
        if current_val == 0 and self.total_value > 0:
            for i in self.indices:
                if self.values[i] > 0:
                    my_offer[i] = 1
                    break

        # Edge case: If we are still asking for everything and it's getting late,
        # concede the least valuable item to keep negotiations moving.
        if sum(my_offer) == sum(self.counts) and self.current_turn > 2:
            for i in reversed(self.indices):
                if my_offer[i] > 0:
                    my_offer[i] -= 1
                    break
                    
        return my_offer