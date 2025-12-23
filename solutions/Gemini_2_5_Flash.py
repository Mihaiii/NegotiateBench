import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me  # 0 if I go first, 1 if I go second
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        
        # current_turn represents the 0-indexed turn number in the negotiation.
        # If me=0, my turns are 0, 2, 4, ...
        # If me=1, my turns are 1, 3, 5, ...
        self.current_turn = 0 
        
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
                # 1. Number available: total_count
                # 2. Number needed to reach target value: 
                #    If current_value is already too high, we don't need any more.
                needed_to_reach_target = (target_value - current_value + value_per_item - 1) // value_per_item if target_value > current_value else 0
                
                num_to_take = min(total_count, needed_to_reach_target)
                
                if num_to_take > 0:
                    my_offer[item_idx] += num_to_take
                    current_value += num_to_take * value_per_item
            else:
                # If value_per_item is 0, we won't add it to reach target_value
                # unless target_value_ratio is 0 and we're trying to give everything away,
                # which is handled by the `if self.total_value_to_me == 0:` case above.
                pass
        
        return my_offer

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Update current_turn only if it's not the very first call of the negotiation.
        # This prevents incrementing current_turn twice for the initial turn (once in __init__, once here).
        if o is not None:
             self.current_turn += 1

        # The total number of turns in the negotiation (mine and partner's).
        # A round is two turns. So, total turns = 2 * max_rounds.
        total_number_of_negotiation_turns = 2 * self.max_rounds

        # Calculate negotiation progress (0.0 to 1.0)
        # Progress is based on the turn number.
        progress = self.current_turn / max(1, total_number_of_negotiation_turns - 1) # max(1,...) to avoid division by zero
        progress = min(progress, 1.0) # Cap progress at 1.0

        # Dynamic demand ratio: start high, decrease over time.
        # Use a non-linear decay to be more stubborn initially and more flexible towards the end.
        initial_demand_ratio = 0.9  # Start by demanding a high percentage
        final_demand_ratio = 0.51   # Aim for slightly above 50% to ensure a win, if possible

        # If all items are worthless to me, I have no preference.
        if self.total_value_to_me == 0:
            demand_ratio = 0.0
        else:
            # Adjust demand based on progress
            # Using a cubic decay for faster reduction towards the end
            # (1 - progress)^3 gives a high value for low progress, quickly drops as progress approaches 1.
            decay_factor = (1 - progress)**3 
            demand_ratio = final_demand_ratio + (initial_demand_ratio - final_demand_ratio) * decay_factor

        # Ensure demand ratio doesn't exceed 1.0 or fall below 0.0
        demand_ratio = max(min(demand_ratio, 1.0), 0.0)

        # Check if it's the last possible turn in the entire negotiation.
        # This is when my decision is final: accept the offer or walk away.
        is_absolute_last_opportunity = (self.current_turn == total_number_of_negotiation_turns - 1)


        # If an offer was made to me:
        if o is not None:
            offer_value = self.calculate_value(o)
            
            # Acceptance conditions:
            # 1. The offer meets or exceeds my current calculated demand ratio.
            # 2. It's the absolute last turn, and the offer provides *any* value to me, preventing a total loss.
            # 3. If everything is worthless to me, and the partner offers me 0, I accept (as 0 is the maximum I can get).
            
            if offer_value >= self.total_value_to_me * demand_ratio:
                return None  # Accept offer
            elif is_absolute_last_opportunity and offer_value > 0:
                # On the very last turn, accept any offer that gives me something, rather than nothing.
                return None
            elif self.total_value_to_me == 0 and offer_value == 0:
                # If I value nothing, and they offer nothing, accept. It's the best I can get.
                return None

        # Create counter-offer (or initial offer)
        my_offer_to_make = self.create_my_offer(demand_ratio)
        
        # If I am making the very last offer of my own before negotiations might end
        # (i.e., if the partner rejects this, there's no more counter-offers from me),
        # I should be more flexible to increase the chance of acceptance.
        # This is the last turn where I can *make* an offer.
        is_my_last_opportunity_to_make_offer = (self.current_turn == total_number_of_negotiation_turns - 2)

        if is_my_last_opportunity_to_make_offer:
            # Be more flexible. Aim for a slightly reduced demand to make it more palatable.
            # But still try to get more than 50% if total_value_to_me > 0.
            flexible_demand_ratio = max(demand_ratio * 0.8, 0.51) 
            if self.total_value_to_me == 0:
                 flexible_demand_ratio = 0.0
            my_offer_to_make = self.create_my_offer(flexible_demand_ratio)
            
        return my_offer_to_make