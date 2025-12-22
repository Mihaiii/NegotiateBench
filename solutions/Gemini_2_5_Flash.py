class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me  # 0 if I go first, 1 if I go second
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.current_round = 0 if me == 0 else 0.5  # Track current round (0.5 for partner's first turn)
        self.total_value_to_me = sum(counts[i] * values[i] for i in range(len(counts)))
        self.num_object_types = len(counts)

    def calculate_value(self, offer_items: list[int]) -> int:
        """Calculates the value of a given offer for me."""
        return sum(self.values[i] * offer_items[i] for i in range(self.num_object_types))

    def create_my_offer(self, min_value_percentage: float) -> list[int]:
        """
        Creates an offer for myself aiming for a certain percentage of the total value.
        It prioritizes getting more valuable items first.
        """
        target_value = int(self.total_value_to_me * min_value_percentage)
        my_offer = [0] * self.num_object_types
        current_value = 0

        # Create a list of tuples (value_per_item, item_index) and sort by value
        item_priorities = sorted(
            [(self.values[i], i) for i in range(self.num_object_types)],
            key=lambda x: x[0],
            reverse=True
        )

        for value_per_item, item_idx in item_priorities:
            for _ in range(self.counts[item_idx]):
                if current_value + value_per_item <= target_value or value_per_item == 0:
                    my_offer[item_idx] += 1
                    current_value += value_per_item
                else:
                    # If adding current item exceeds target, and it's not worthless,
                    # try to see if we can add it without taking us too far over.
                    # Or just move to the next item type.
                    pass
        
        # If we still haven't reached the target value, try to grab more valuable items
        # up to their count, even if it exceeds the target slightly.
        for value_per_item, item_idx in item_priorities:
            remaining_to_take = self.counts[item_idx] - my_offer[item_idx]
            for _ in range(remaining_to_take):
                if current_value < target_value or value_per_item > 0: # Always try to take valuable items if target not met
                    my_offer[item_idx] += 1
                    current_value += value_per_item

        return my_offer

    def offer(self, o: list[int] | None) -> list[int] | None:
        if self.me == 0:
            self.current_round += 0.5 # I'm making an offer
        else:
            if o is not None:
                self.current_round += 1 # Partner made an offer, so a full round passed
            
        current_round_num = int(self.current_round)

        # Define negotiation strategy based on rounds remaining
        # As rounds decrease, I become more flexible (lower my demand)
        # This is a simple linear decrease from 90% down to 50%
        # Example:
        # Max 5 rounds:
        # Round 1: 0.90 -> 0.85 -> 0.80 -> 0.75 -> 0.70 -> 0.65 -> 0.60 -> 0.55 -> 0.50
        # If first turn (me=0), then self.current_round is 0.5, 1.5, 2.5, 3.5, 4.5
        # If second turn (me=1), then self.current_round is 1, 2, 3, 4, 5

        # Calculate a dynamic minimum value percentage I am willing to accept or demand.
        # This percentage will decrease as negotiations progress, reflecting increased
        # willingness to compromise to avoid ending up with nothing.
        
        # Start demanding/accepting a high percentage, and gradually decrease it.
        # Let's say we start at 90% and go down to 50%
        initial_min_val_percentage = 0.90
        final_min_val_percentage = 0.50
        
        # Calculate how much the percentage should drop per turn
        # A full "round" consists of two turns. max_rounds * 2 is total turns.
        # We need to consider actual turns, not rounds.
        total_turns = self.max_rounds * 2
        
        # How many turns have passed counting from 0?
        # If me=0, offers will be on turn 0, 2, 4,... (current_round=0.5, 1.5, 2.5, ...)
        # If me=1, offers will be on turn 1, 3, 5,... (current_round=1, 2, 3, ...)
        
        if self.me == 0:
            turns_taken = 2 * (current_round_num) # my offer on turn 0, 2, 4 etc.
        else: # me == 1
            turns_taken = 2 * (current_round_num - 1) + 1 # my offer on turn 1, 3, 5 etc.
        
        if total_turns > 1: # Avoid division by zero
            reduction_per_turn = (initial_min_val_percentage - final_min_val_percentage) / (total_turns - 1)
        else:
            reduction_per_turn = 0 # Only one turn possible

        my_required_percentage = max(final_min_val_percentage, initial_min_val_percentage - (turns_taken * reduction_per_turn))
        
        # If it's the very last turn, accept anything above a very low threshold to avoid getting nothing
        is_last_turn = (turns_taken + 1 >= total_turns)

        if o is not None:
            # Evaluate partner's offer
            offer_value = self.calculate_value(o)
            
            if is_last_turn and offer_value > 0: # On the last turn, accept any positive offer
                 return None
            
            if offer_value >= self.total_value_to_me * my_required_percentage:
                return None  # Accept offer if it meets my current required percentage

        # If turn is first and o is None, or I don't accept partner's offer, make a counter-offer
        return self.create_my_offer(my_required_percentage)