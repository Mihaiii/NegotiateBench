import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me  # 0 if I go first, 1 if I go second
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        
        # current_turn represents the 0-indexed turn number in the negotiation.
        # My turn number will be 0, 2, 4... if I go first (me=0).
        # My turn number will be 1, 3, 5... if I go second (me=1).
        # We initialize it based on 'me' and increment it in 'offer'.
        self.current_turn = me 
        
        self.total_value_to_me = sum(counts[i] * values[i] for i in range(len(counts)))
        self.num_object_types = len(counts)

    def calculate_value(self, offer_items: list[int]) -> int:
        """Calculates the value of a given offer for me."""
        return sum(self.values[i] * offer_items[i] for i in range(self.num_object_types))

    def create_my_offer(self, target_value_ratio: float) -> list[int]:
        """
        Creates an offer for myself aiming for a certain percentage (ratio) of the total value.
        It prioritizes getting more valuable items first while respecting counts.
        """
        
        # If total_value_to_me is 0, we can't aim for a ratio of it. Just return 0 for everything.
        if self.total_value_to_me == 0:
            return [0] * self.num_object_types

        # Ensure target_value_ratio is within a valid range [0, 1]
        target_value_ratio = max(0.0, min(1.0, target_value_ratio))
        target_value = int(self.total_value_to_me * target_value_ratio)
        my_offer = [0] * self.num_object_types
        current_value = 0
        
        # Create a list of tuples: (value_per_item, item_index, available_count)
        # Sort by value_per_item in descending order.
        item_info = []
        for i in range(self.num_object_types):
            item_info.append((self.values[i], i, self.counts[i]))
        item_info.sort(key=lambda x: x[0], reverse=True)

        # Iterate through items, trying to add them to the offer
        for value_per_item, item_idx, total_count in item_info:
            if current_value >= target_value:
                break

            if value_per_item > 0:
                # Calculate how many of this item we can take
                # Number needed to reach target value: 
                needed_to_reach_target = (target_value - current_value + value_per_item - 1) // value_per_item 
                
                num_to_take = min(total_count, needed_to_reach_target)
                
                if num_to_take > 0:
                    my_offer[item_idx] += num_to_take
                    current_value += num_to_take * value_per_item
            else:
                # If value_per_item is 0, we only take them if we haven't reached our target and
                # there are no other valuable items left to cover the target.
                # However, since we sort by value and prioritize, by the time we get to 0-value items,
                # we are likely trying to reach the minimum acceptable.
                # For now, we mainly focus on valuable items to reach the target.
                pass
        
        return my_offer

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Increment current_turn only if it's not the very first call.
        # When o is None, it's the very first call, and current_turn is already set by __init__.
        if o is not None:
            self.current_turn += 2 # My turn comes every two turns

        # The total number of turns in the negotiation (mine and partner's).
        total_possible_turns = 2 * self.max_rounds

        # Calculate negotiation progress (0.0 to 1.0)
        # progress is based on the current turn index (0-indexed) relative to total_possible_turns.
        # Using max(1, ...) to avoid division by zero if max_rounds somehow is 0 or 0 total turns.
        progress = self.current_turn / max(1, total_possible_turns - 1)
        progress = min(progress, 1.0) # Cap progress at 1.0

        # Dynamic demand ratio: start high, decrease over time.
        # Use a non-linear decay to be more stubborn initially and more flexible towards the end.
        initial_demand_ratio = 0.95  # Start by demanding a very high percentage
        final_demand_ratio = 0.51   # Aim for slightly above 50% to ensure a win, if possible.

        # If all items are worthless to me, I have no preference.
        if self.total_value_to_me == 0:
            demand_ratio = 0.0
        else:
            # Adjust demand based on progress
            # Using a cubic decay for faster reduction towards the end
            # (1 - progress)^2 gives a good balance. A higher exponent makes it more stubborn longer.
            decay_factor = (1 - progress)**2 
            demand_ratio = final_demand_ratio + (initial_demand_ratio - final_demand_ratio) * decay_factor

        # Ensure demand ratio doesn't exceed 1.0 or fall below 0.0
        demand_ratio = max(min(demand_ratio, 1.0), 0.0)

        # Check if it's the last possible turn for *me* to accept an offer.
        # This is when my decision is final before negotiations fail.
        is_absolute_final_acceptance_turn = (self.current_turn == total_possible_turns - 1)

        # If an offer was made to me:
        if o is not None:
            offer_value = self.calculate_value(o)
            
            # Acceptance conditions:
            # 1. The offer meets or exceeds my current calculated demand ratio.
            # 2. It's the absolute last turn, and the offer provides *any* positive value to me, preventing a total loss.
            # 3. If everything is worthless to me, and the partner offers me 0, I accept (as 0 is the maximum I can get).
            
            if offer_value >= self.total_value_to_me * demand_ratio:
                return None  # Accept offer
            elif is_absolute_final_acceptance_turn and offer_value > 0:
                # On the very last turn, accept any offer that gives me something, rather than nothing.
                return None
            elif self.total_value_to_me == 0 and offer_value == 0:
                # If I value nothing, and they offer nothing, accept. It's the inevitable outcome.
                return None

        # Create counter-offer (or initial offer)
        my_offer_to_make = self.create_my_offer(demand_ratio)
        
        # Consider being more flexible on my *last chance to make an offer* if the deal hasn't closed.
        # This is the turn before the partner's last acceptance turn.
        is_my_last_chance_to_make_offer = (self.current_turn == total_possible_turns - 2)

        if is_my_last_chance_to_make_offer:
            # Be more flexible. Aim for a slightly reduced demand to make it more palatable for the opponent.
            # We want to ensure at least 50% if possible to make a deal.
            # A linear decay of flexibility, but capping at a minimum.
            flexible_demand_ratio = max(demand_ratio * 0.9, 0.51) 
            if self.total_value_to_me == 0:
                 flexible_demand_ratio = 0.0
            
            # Recreate offer with higher flexibility
            my_offer_to_make = self.create_my_offer(flexible_demand_ratio)
            
        return my_offer_to_make