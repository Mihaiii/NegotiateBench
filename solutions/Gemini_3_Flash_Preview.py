class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.turn_count = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Priority list based on value per item
        self.priority = sorted(range(len(counts)), key=lambda i: self.values[i], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # Total turns allowed is max_rounds * 2. 
        # But turn_count increments every time THIS agent is called.
        # Max calls to this method is max_rounds.
        
        if o is not None:
            offer_value = sum(v * count for v, count in zip(self.values, o))
            
            # Acceptance logic
            if self.turn_count >= self.max_rounds:
                # Absolute last chance for this agent
                return None if offer_value > 0 else self._make_offer(0.5)
            
            threshold = self._get_threshold()
            if offer_value >= threshold:
                return None

        return self._make_offer(self._get_threshold())

    def _get_threshold(self) -> float:
        """Determines the minimum acceptable value based on progress."""
        progress = self.turn_count / self.max_rounds
        if progress < 0.2:
            return self.total_value * 0.95
        if progress < 0.5:
            return self.total_value * 0.85
        if progress < 0.8:
            return self.total_value * 0.75
        if progress < 0.95:
            return self.total_value * 0.6
        return self.total_value * 0.51

    def _make_offer(self, target_value: float) -> list[int]:
        """Constructs an offer greedily prioritizing internal value."""
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Always try to keep items we value until we hit target
        for i in self.priority:
            if self.values[i] > 0:
                for _ in range(self.counts[i]):
                    if current_val < target_value:
                        my_offer[i] += 1
                        current_val += self.values[i]
                    else:
                        break
        
        # Strategy for worthless items:
        # Early on, hold them to signal they might be valuable (bargaining chips).
        # Late game, give them all to the partner to "sweeten" their perceived deal.
        progress = self.turn_count / self.max_rounds
        for i in range(len(self.counts)):
            if self.values[i] == 0:
                if progress < 0.5:
                    my_offer[i] = self.counts[i] // 2
                else:
                    my_offer[i] = 0
        
        # Ensure we always ask for at least something if there is value to be had
        if current_val == 0 and self.total_value > 0:
            my_offer[self.priority[0]] = 1
            
        return my_offer