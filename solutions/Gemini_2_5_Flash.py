class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me  # 0 if I go first, 1 if I go second
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        
        self.current_round = 0.0
        # If I go second, the first round has technically started, and the opponent has made their offer.
        if me == 1:
            self.current_round = 0.5 
        
        self.total_value_to_me = sum(counts[i] * values[i] for i in range(len(counts)))
        self.num_object_types = len(counts)
        
        # Initial demand for opponent to receive. We expect them to concede over time.
        # Starting with a high demand for myself means a low concession to the opponent.
        self.initial_self_demand_ratio = 1.0 

    def calculate_value(self, offer_items: list[int]) -> int:
        """Calculates the value of a given offer for me."""
        return sum(self.values[i] * offer_items[i] for i in range(self.num_object_types))

    def create_my_offer(self, target_value_ratio: float) -> list[int]:
        """
        Creates an offer for myself aiming for a certain percentage (ratio) of the total value.
        It prioritizes getting more valuable items first while respecting counts.
        """
        
        # If I value nothing, I should offer to take nothing.
        if self.total_value_to_me == 0:
            return [0] * self.num_object_types

        # Ensure target_value_ratio is within [0.0, 1.0]
        target_value_ratio = max(0.0, min(1.0, target_value_ratio))
        target_value = int(self.total_value_to_me * target_value_ratio)
        
        my_offer_counts = [0] * self.num_object_types
        current_value = 0
        
        # Create a list of (value_per_item, item_index) tuples and sort by value_per_item descending.
        # This ensures we prioritize getting more valuable items first.
        item_info = []
        for i in range(self.num_object_types):
            item_info.append((self.values[i], i))
        item_info.sort(key=lambda x: x[0], reverse=True)

        for value_per_item, item_idx in item_info:
            if current_value >= target_value:
                break # Reached or exceeded target value

            if value_per_item > 0: # Only consider items with positive value to reach the target
                num_can_take = self.counts[item_idx]
                
                # Calculate how many items of this type are needed to reach the target value
                # taking into account current value and the item's value.
                # Use max(0, ...) to prevent negative numbers if current_value already high
                needed_for_target = (target_value - current_value + value_per_item - 1) // value_per_item
                
                num_to_take = min(num_can_take, needed_for_target)
                
                my_offer_counts[item_idx] += num_to_take
                current_value += num_to_take * value_per_item
        
        # After attempting to meet the target value with positive-valued items,
        # assign remaining items. For items with zero value to me, I'm indifferent.
        # The strategy here is to take all items that are worthless to me, as they don't affect my value,
        # and it simplifies the offer. This might be perceived as aggressive, but it maximizes my share
        # while keeping my value calculation simple.
        for i in range(self.num_object_types):
            if self.values[i] == 0:
                my_offer_counts[i] = self.counts[i] 

        # Ensure that the offer does not exceed available counts
        for i in range(self.num_object_types):
            my_offer_counts[i] = min(my_offer_counts[i], self.counts[i])

        return my_offer_counts

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is None:  # This is my very first offer in the negotiation
            # self.current_round is already 0.0 or 0.5 based on self.me
            pass
        else: # An offer was received from the partner
            self.current_round += 0.5 # Increment my turn counter

        # Calculate negotiation progress (0.0 to 1.0)
        # Using self.current_round relative to max_rounds.
        # The negotiation ends when current_round >= max_rounds.
        progress = self.current_round / self.max_rounds
        progress = min(progress, 1.0) # Cap progress at 1.0

        # Define the range of acceptable value.
        # I always want at least half of the total perceived value.
        min_acceptable_value_ratio = 0.5
        if self.total_value_to_me == 0:
            min_acceptable_value_ratio = 0.0 # If I value nothing, I'll accept 0.

        # Dynamic concession strategy:
        # Start demanding self.initial_self_demand_ratio (1.0).
        # Gradually concede towards min_acceptable_value_ratio as rounds progress.
        # Using a cubic function for faster concession towards the end.
        
        # The fraction of the negotiation remaining (1.0 at start, 0.0 at end)
        remaining_negotiation_fraction = 1.0 - progress
        
        # Calculate my current demand ratio. This ratio reduces from initial_self_demand_ratio
        # down to min_acceptable_value_ratio as progress goes from 0 to 1.
        # The cubic function (remaining_negotiation_fraction**3) makes concessions faster later.
        current_self_demand_ratio = min_acceptable_value_ratio + \
                                    (self.initial_self_demand_ratio - min_acceptable_value_ratio) * \
                                    (remaining_negotiation_fraction ** 2) # Changed to square for smoother initial decline

        # Ensure demand ratio is within valid bounds.
        current_self_demand_ratio = max(min(current_self_demand_ratio, 1.0), 0.0)

        # Determine if this is the last possible turn to make a deal.
        # If I'm turn 0, my last chance to accept is at max_rounds - 0.5 (opponent's offer in last round)
        # If I'm turn 1, my last chance to accept is at max_rounds (opponent's offer when my current_round hits max_rounds)
        # This condition verifies if no more counter-offers can be made by ME after this turn.
        can_make_another_offer = (self.current_round < self.max_rounds - 0.5)

        # Handle incoming offer from partner
        if o is not None:
            offer_value = self.calculate_value(o)
            
            # Acceptance conditions:
            # 1. The offer meets or exceeds my current calculated demand.
            # 2. It's truly the last possible turn and the offer gives me something (or I value nothing), to avoid no-deal.
            
            if offer_value >= self.total_value_to_me * current_self_demand_ratio:
                return None  # Accept offer

            # If no more offers can be made by me and the offer provides *any* value (or I value nothing), accept.
            # This is to prevent a no-deal scenario when time runs out.
            if not can_make_another_offer: # This means after this turn, negotiation will end if I don't accept.
                if offer_value > 0 or self.total_value_to_me == 0:
                    return None
            
        # If no offer was accepted, or if it's my first turn, create a counter-offer.
        my_offer_to_make = self.create_my_offer(current_self_demand_ratio)
        
        # Before returning the offer, perform one last check for validity
        # An offer is valid if:
        # 1. All counts are non-negative.
        # 2. No count exceeds the remaining total count for that item type.
        
        for i in range(self.num_object_types):
            if my_offer_to_make[i] < 0:
                my_offer_to_make[i] = 0
            if my_offer_to_make[i] > self.counts[i]:
                my_offer_to_make[i] = self.counts[i]
                
        return my_offer_to_make