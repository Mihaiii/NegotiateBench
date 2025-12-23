import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me  # 0 if I go first, 1 if I go second
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        
        self.current_turn = me 
        
        self.total_value_to_me = sum(counts[i] * values[i] for i in range(len(counts)))
        self.num_object_types = len(counts)
        
        # Store initial demand ratio and a memory of past offers
        self.initial_demand_ratio = 1.0  # Start by demanding everything
        self.my_last_offer = None # To remember what I offered last

    def calculate_value(self, offer_items: list[int]) -> int:
        """Calculates the value of a given offer for me."""
        return sum(self.values[i] * offer_items[i] for i in range(self.num_object_types))

    def create_my_offer(self, target_value_ratio: float, other_offer: list[int] | None = None) -> list[int]:
        """
        Creates an offer for myself aiming for a certain percentage (ratio) of the total value.
        It prioritizes getting more valuable items first while respecting counts.
        If other_offer is provided, it tries to create a fair counter-offer.
        """
        
        # If total_value_to_me is 0, we can't aim for a ratio of it. Just return 0 for everything.
        if self.total_value_to_me == 0:
            return [0] * self.num_object_types

        # Ensure target_value_ratio is within a valid range [0, 1]
        target_value_ratio = max(0.0, min(1.0, target_value_ratio))
        target_value = int(self.total_value_to_me * target_value_ratio)
        my_offer_counts = [0] * self.num_object_types
        current_value = 0
        
        # Sort items by value_per_item in descending order.
        # Store (value_per_item, item_index)
        item_info = []
        for i in range(self.num_object_types):
            if self.values[i] > 0: # Prioritize valuable items
                item_info.append((self.values[i], i))
        item_info.sort(key=lambda x: x[0], reverse=True)

        # Iterate through items, trying to add them to the offer to reach the target_value
        for value_per_item, item_idx in item_info:
            if current_value >= target_value:
                break

            remaining_count = self.counts[item_idx] - my_offer_counts[item_idx]
            if remaining_count > 0:
                num_to_take = min(remaining_count, (target_value - current_value) // value_per_item)
                if (target_value - current_value) % value_per_item != 0 and num_to_take < remaining_count:
                    num_to_take += 1 # Take one more to potentially exceed or exactly hit target

                if num_to_take > 0:
                    my_offer_counts[item_idx] += num_to_take
                    current_value += num_to_take * value_per_item

        # After fulfilling target value with valuable items, distribute remaining zero-value items if needed
        # Or if the target was 0, distribute all according to some heuristic (e.g., all to partner)
        for i in range(self.num_object_types):
            # If current_value is still less than target_value and we have zero-value items,
            # we fill them up to create a more 'complete' offer, but they don't contribute to value.
            # This part is largely for completeness if the target is very low or 0.
            if self.values[i] == 0:
                my_offer_counts[i] = self.counts[i] # Take all worthless items for a fairer distribution

        # Ensure that the offer does not exceed available counts
        for i in range(self.num_object_types):
            my_offer_counts[i] = min(my_offer_counts[i], self.counts[i])
            
        return my_offer_counts

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Increment current_turn only if it's not the very first call.
        if o is not None:
            self.current_turn += 2 # My turn comes every two turns

        total_possible_turns = 2 * self.max_rounds

        # Calculate negotiation progress (0.0 to 1.0)
        progress = self.current_turn / max(1, total_possible_turns - 1)
        progress = min(progress, 1.0) # Cap progress at 1.0

        # Dynamic demand ratio: start high, decrease over time.
        # Use a non-linear decay to be more stubborn initially and more flexible towards the end.
        
        # Start demanding 100% and go down to just above 50%
        # Experiment with different decay functions. Quadratic decay: (1 - progress)^2
        # This makes the agent more stubborn earlier and more willing to concede later.
        
        # Minimum acceptable value.
        # If total_value_to_me is 0, any offer including 0 value is acceptable.
        if self.total_value_to_me == 0:
            final_demand_ratio = 0.0
        else:
            final_demand_ratio = 0.51 # Aim for slightly above 50% to ensure a win, if possible.

        decay_factor = (1 - progress) ** 2 # Quadratic decay
        demand_ratio = final_demand_ratio + (self.initial_demand_ratio - final_demand_ratio) * decay_factor

        # Ensure demand ratio doesn't exceed 1.0 or fall below 0.0
        demand_ratio = max(min(demand_ratio, 1.0), 0.0)

        # Check if it's the last possible turn for *me* to accept an offer.
        is_absolute_final_acceptance_turn = (self.current_turn == total_possible_turns - 1)

        # If an offer was made to me:
        if o is not None:
            offer_value = self.calculate_value(o)
            
            # Acceptance conditions:
            # 1. The offer meets or exceeds my current calculated demand ratio.
            # 2. It's the absolute last turn, and the offer provides *any* positive value to me, preventing a total loss.
            # 3. If everything is worthless to me, and the partner offers me 0, I accept.
            
            if offer_value >= self.total_value_to_me * demand_ratio:
                return None  # Accept offer
            elif is_absolute_final_acceptance_turn and offer_value > 0:
                # On the very last turn, accept any offer that gives me something, rather than nothing.
                return None
            elif self.total_value_to_me == 0 and offer_value == 0:
                # If I value nothing, and they offer nothing, accept. It's the inevitable outcome.
                return None

        # Determine if it's my last chance to make an offer.
        # This is the turn before the partner's last acceptance turn.
        is_my_last_chance_to_make_offer = (self.current_turn == total_possible_turns - 2)

        # Create counter-offer (or initial offer)
        my_offer_to_make = self.create_my_offer(demand_ratio)
        
        # If it's my last chance to make an offer, make a slightly more generous offer
        # to increase the chances of a deal, but still aim for a reasonable outcome.
        if is_my_last_chance_to_make_offer:
            # We want to ensure at least 50% if possible to make a deal.
            # Gradually reduce demand towards the final_demand_ratio.
            flexible_demand_ratio = max(demand_ratio * 0.9, final_demand_ratio)
            if self.total_value_to_me == 0:
                 flexible_demand_ratio = 0.0
            
            my_offer_to_make = self.create_my_offer(flexible_demand_ratio)
            
        self.my_last_offer = my_offer_to_make # Store my last offer
        return my_offer_to_make