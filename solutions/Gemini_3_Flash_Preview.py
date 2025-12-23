class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.current_turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        # Sort indices by value density (though density is just value here as weights are 1)
        self.indices = sorted(range(len(counts)), key=lambda i: values[i], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is not None:
            self.current_turn += 1
        
        # Calculate utility of the offer received (o is what we get)
        received_val = sum(o[i] * self.values[i] for i in range(len(o))) if o is not None else 0
        
        # progress goes from 0 to 1
        progress = self.current_turn / self.total_turns

        # 1. Decision to Accept
        if o is not None:
            # Acceptance thresholds: start high, drop to reach a deal
            if progress < 0.2:
                threshold = 0.9 * self.total_value
            elif progress < 0.5:
                threshold = 0.8 * self.total_value
            elif progress < 0.7:
                threshold = 0.65 * self.total_value
            elif progress < 0.9:
                threshold = 0.5 * self.total_value
            else:
                # In the final turns, accept anything above 25% or even 1 if it's the very last chance
                threshold = 0.25 * self.total_value if self.current_turn < self.total_turns - 1 else 1
            
            if received_val >= max(threshold, 1):
                return None

        # 2. Counter-offer Logic
        self.current_turn += 1
        
        # Target a percentage of the total value
        if progress < 0.1:
            target_ratio = 1.0
        elif progress < 0.4:
            target_ratio = 0.9
        elif progress < 0.7:
            target_ratio = 0.75
        elif progress < 0.9:
            target_ratio = 0.6
        else:
            target_ratio = 0.4
            
        return self._create_offer(target_ratio)

    def _create_offer(self, target_ratio: float) -> list[int]:
        target_val = target_ratio * self.total_value
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Greedily take items that are valuable to us
        for i in self.indices:
            if self.values[i] == 0:
                continue
            for _ in range(self.counts[i]):
                if current_val + self.values[i] <= target_val or current_val == 0:
                    my_offer[i] += 1
                    current_val += self.values[i]
                else:
                    break
        
        # Concession: If we are asking for everything, give away the least valuable item to show movement
        if sum(my_offer) == sum(self.counts) and self.total_value > 0:
            # Drop the cheapest item we have in our offer
            for i in reversed(self.indices):
                if my_offer[i] > 0:
                    my_offer[i] -= 1
                    break
                    
        # Final check: ensure we aren't returning a completely empty offer if there is value to be had
        if sum(my_offer) == 0 and self.total_value > 0:
            my_offer[self.indices[0]] = 1
            
        return my_offer