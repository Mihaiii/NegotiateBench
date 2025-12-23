class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me  # 0 if I go first, 1 if I go second
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        
        self.current_turn = 0.0
        # If I go second, the first round has technically started, and the opponent has made their offer.
        if me == 1:
            self.current_turn = 0.5 
        
        self.total_value_to_me = sum(counts[i] * values[i] for i in range(len(counts)))
        self.num_object_types = len(counts)
        
        # Initial demand for opponent to receive. We expect them to concede over time.
        # Starting with a high demand for myself means a low concession to the opponent.
        # This can be adjusted based on desired aggressiveness.
        self.initial_self_demand_ratio = 0.9  # Start by demanding 90% of my total value
        self.min_acceptable_value_ratio = 0.51 # Will accept a minimum of 51% of my total value

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

        # First, try to get items that have value to me
        for value_per_item, item_idx in item_info:
            if current_value >= target_value:
                break 

            if value_per_item > 0: 
                num_can_take = self.counts[item_idx]
                
                # Calculate how many items of this type are needed to reach the target value
                # taking into account current value and the item's value.
                # Use max(0, ...) to prevent negative numbers if current_value already high
                needed_for_target = (target_value - current_value + value_per_item - 1) // value_per_item
                
                num_to_take = min(num_can_take, needed_for_target)
                
                my_offer_counts[item_idx] += num_to_take
                current_value += num_to_take * value_per_item
        
        # Then, fill up any remaining valuable items that were not taken to reach the target, up to their full count.
        # This ensures we take all positive-valued items we want, even if they exceed the target value slightly.
        for value_per_item, item_idx in item_info:
            if value_per_item > 0:
                num_already_taken = my_offer_counts[item_idx]
                num_can_still_take = self.counts[item_idx] - num_already_taken
                my_offer_counts[item_idx] += num_can_still_take

        # For items with zero value to me, I'm indifferent.
        # The strategy here is to take all items that are worthless to me, as they don't affect my value,
        # but they might have value to the opponent, thus reducing what they get.
        for i in range(self.num_object_types):
            if self.values[i] == 0:
                my_offer_counts[i] = self.counts[i] 

        # Ensure that the offer does not exceed available counts, this is a final safeguard.
        for i in range(self.num_object_types):
            my_offer_counts[i] = min(my_offer_counts[i], self.counts[i])

        return my_offer_counts

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is None:  # This is my very first offer in the negotiation
            # current_turn is already 0.0 or 0.5 based on self.me
            pass
        else: # An offer was received from the partner
            self.current_turn += 0.5 # Increment my turn counter

        # Calculate negotiation progress (0.0 to 1.0)
        # Using self.current_turn relative to max_rounds * 2 (total turns).
        # max_rounds is total rounds, so max_rounds * 2 is total turns.
        # If max_rounds is 16, total turns are 32.
        # current_turn goes from 0 to (2*max_rounds - 1) or (2*max_rounds - 0.5)
        
        # Normalizing current_turn by total possible turns to get progress from 0 to 1
        total_possible_turns = 2 * self.max_rounds
        progress = self.current_turn / total_possible_turns
        progress = min(progress, 1.0) # Cap progress at 1.0

        # Dynamic concession strategy:
        # Gradually concede from initial_self_demand_ratio towards min_acceptable_value_ratio as time progresses.
        # Using a quadratic function for concession to make it smoother and concede faster towards the end.
        
        # The fraction of the negotiation remaining (1.0 at start, 0.0 at end)
        remaining_negotiation_fraction = 1.0 - progress
        
        # Calculate my current demand ratio. This ratio reduces from initial_self_demand_ratio
        # down to min_acceptable_value_ratio as progress goes from 0 to 1.
        # (remaining_negotiation_fraction ** 2) makes concessions increase as negotiation progresses.
        
        # Linear interpolation between initial_self_demand_ratio and min_acceptable_value_ratio,
        # with a bias towards initial_self_demand_ratio early on due to the quadratic term.
        current_self_demand_ratio = self.min_acceptable_value_ratio + \
                                    (self.initial_self_demand_ratio - self.min_acceptable_value_ratio) * \
                                    (remaining_negotiation_fraction ** 2) 

        # Ensure demand ratio is within valid bounds.
        current_self_demand_ratio = max(min(current_self_demand_ratio, 1.0), 0.0)

        # Determine if this is the last possible turn to make a deal.
        # A round is an exchange of two offers. max_rounds * 2 is the total turn budget.
        # My last turn to ACCEPT would be when current_turn is total_possible_turns - 0.5 (if first)
        # or total_possible_turns (if second, which implies opponent's turn is already over)
        
        # We need to make sure that if we counter-offer, there's still a turn for the other agent to respond.
        # If I am player 0 (first, current_turn=0, 1, 2, ...):
        # My last possible *counter-offer* is at current_turn = total_possible_turns - 1 (e.g., if total 32 turns, my last counter is turn 31).
        # This gives the opponent turn 31.5 to accept.
        # My last possible *acceptance* is at current_turn = total_possible_turns - 0.5 (opponent's offer).
        
        # If I am player 1 (second, current_turn=0.5, 1.5, 2.5, ...):
        # My last possible *counter-offer* is at current_turn = total_possible_turns - 0.5 (e.g., if total 32 turns, my last counter is turn 31.5).
        # This means the opponent has no turn left.
        # My last possible *acceptance* is at current_turn = total_possible_turns (opponent's offer).
        
        # For simplicity, let's consider if my *next* action would exceed the negotiation limit.
        # If I make an offer, it increments current_turn by 0.5 for the opponent and then another 0.5 for me.
        # So if current_turn + 1.0 > total_possible_turns, I cannot make another offer.
        
        # The number of available *slots* for offers is total_possible_turns.
        # If o is None (my first offer), self.current_turn is 0.0 or 0.5.
        # I can offer if self.current_turn < total_possible_turns - 0.5 (opponent needs a slot)
        can_make_another_offer = (self.current_turn < total_possible_turns - 0.5)

        # Handle incoming offer from partner
        if o is not None:
            offer_value = self.calculate_value(o)
            
            # Acceptance conditions:
            # 1. The offer meets or exceeds my current calculated demand.
            # 2. It's truly the last possible turn and the offer gives me something (or I value nothing), to avoid no-deal.
            
            if offer_value >= self.total_value_to_me * current_self_demand_ratio:
                return None  # Accept offer

            # If no more offers can be made by me, and the offer provides *any* value (or I value nothing), accept.
            # This is a critical no-deal avoidance strategy at the very end.
            if not can_make_another_offer:
                if offer_value >= self.total_value_to_me * self.min_acceptable_value_ratio or self.total_value_to_me == 0:
                    return None
            
        # If no offer was accepted, or if it's my first turn, create a counter-offer.
        my_offer_to_make = self.create_my_offer(current_self_demand_ratio)
        
        # Final validation of the offer (should already be handled by create_my_offer, but good safeguard)
        for i in range(self.num_object_types):
            if my_offer_to_make[i] < 0:
                my_offer_to_make[i] = 0
            if my_offer_to_make[i] > self.counts[i]:
                my_offer_to_make[i] = self.counts[i]
                
        return my_offer_to_make