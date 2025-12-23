class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.current_round = 0
        self.total_turns = max_rounds * 2
        self.turn_count = 0
        
        # Calculate total possible value
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Sort indices by value density (highest value per item first)
        self.indices_by_value = sorted(
            range(len(counts)), 
            key=lambda i: self.values[i], 
            reverse=True
        )

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # Calculate value of partner's offer if it exists
        if o is not None:
            offer_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance Logic:
            # 1. Accept if it's a very good deal (>= 80% total value)
            # 2. Accept if it's the very last turn and we get anything > 0
            # 3. Gradually lower acceptance threshold from 80% to 50%
            threshold_ratio = 0.8 - (0.3 * (self.turn_count / self.total_turns))
            if offer_value >= self.total_value * threshold_ratio:
                return None
            
            # If it's our last possible turn and the offer is better than nothing, take it
            if self.turn_count >= self.total_turns - 1 and offer_value > 0:
                return None

        # Counter-offer Logic:
        # Determine how much we want to demand based on the current round.
        # Early rounds: Demand 100-90%. Late rounds: Demand ~60-70%.
        target_ratio = 1.0 - (0.4 * (self.turn_count / self.total_turns))
        target_value = self.total_value * target_ratio
        
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Build offer by taking most valuable items first
        for i in self.indices_by_value:
            for _ in range(self.counts[i]):
                if current_val + self.values[i] <= target_value or not any(my_offer):
                    my_offer[i] += 1
                    current_val += self.values[i]
                else:
                    break
        
        # Ensure we don't return an empty offer if we have valuable items
        if sum(my_offer) == 0:
            for i in self.indices_by_value:
                if self.counts[i] > 0:
                    my_offer[i] = 1
                    break

        return my_offer