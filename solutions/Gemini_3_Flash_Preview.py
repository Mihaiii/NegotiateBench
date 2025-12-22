class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.current_round = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Sort items by value density (value to us)
        self.items_by_value = sorted(
            range(len(counts)), 
            key=lambda i: self.values[i], 
            reverse=True
        )

    def offer(self, o: list[int] | None) -> list[int] | None:
        if self.me == 1: # Increment round count if we are second mover
            self.current_round += 1
            
        # 1. Evaluate partner's offer
        if o is not None:
            offer_value = sum(v * count for v, count in zip(self.values, o))
            
            # Acceptance Logic:
            # - Accept if it's the last round and we get > 0
            # - Accept if value is "good enough" based on time remaining
            threshold = self.total_value * self._get_threshold_ratio()
            if offer_value >= threshold:
                return None
            if self.current_round >= self.max_rounds - 1 and offer_value > 0:
                return None

        # 2. Increment round count if we are first mover
        if self.me == 0:
            self.current_round += 1

        # 3. Create a counter-offer
        return self._create_offer()

    def _get_threshold_ratio(self) -> float:
        """Determines how much we are willing to concede based on time."""
        progress = self.current_round / self.max_rounds
        if progress < 0.2:
            return 0.9  # Ask for a lot early
        if progress < 0.5:
            return 0.8
        if progress < 0.8:
            return 0.7
        return 0.61  # Final stages: accept more than half

    def _create_offer(self) -> list[int]:
        """Greedily pick items to satisfy target value, prioritizing what we value."""
        target_ratio = self._get_threshold_ratio() + 0.1 # Try to get more than our limit
        target_value = self.total_value * min(0.95, target_ratio)
        
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Priority 1: Take items that are worth something to us
        for i in self.items_by_value:
            if self.values[i] > 0:
                for _ in range(self.counts[i]):
                    if current_val < target_value:
                        my_offer[i] += 1
                        current_val += self.values[i]
                    else:
                        break
        
        # Priority 2: In early game, don't give away items that are worthless to us 
        # but might be valuable to them (prevents appearing too desperate).
        # In late game, give away worthless items to sweeten the deal.
        if self.current_round < self.max_rounds * 0.7:
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    my_offer[i] = self.counts[i] // 2 
        else:
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    my_offer[i] = 0

        # Ensure we don't return an empty offer if we want something
        if sum(my_offer) == 0 and self.total_value > 0:
            my_offer[self.items_by_value[0]] = 1
            
        return my_offer