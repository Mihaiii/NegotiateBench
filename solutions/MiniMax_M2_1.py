class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.total = sum(counts[i] * values[i] for i in range(len(counts)))
        self.total_turns = 2 * max_rounds
        self.turns = 0
        self.current_demand = counts[:]  # Start demanding everything

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turns += 1
        remaining_turns = self.total_turns - self.turns + 1
        half = self.total / 2
        
        # Calculate target value for this turn (interpolating from total to half)
        if self.total_turns > 1:
            target_value = half + (self.total - half) * ((remaining_turns - 1) / (self.total_turns - 1))
        else:
            target_value = half

        # Check if we accept the partner's offer
        if o is not None:
            offered_value = sum(o[i] * self.values[i] for i in range(len(o)))
            if offered_value >= target_value:
                return None  # Accept

        # Adjust our demand by removing objects until value <= target_value
        while True:
            current_value = sum(self.current_demand[i] * self.values[i] for i in range(len(self.current_demand)))
            if current_value <= target_value:
                break
            
            # Find object type with smallest value per unit that we still have
            min_index = -1
            min_value = float('inf')
            for i in range(len(self.current_demand)):
                if self.current_demand[i] > 0 and self.values[i] < min_value:
                    min_value = self.values[i]
                    min_index = i
            
            if min_index == -1:
                break  # No more objects to remove
            
            # Remove one object of the least valued type
            self.current_demand[min_index] -= 1
        
        return self.current_demand