import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me  # 0 if I go first, 1 if I go second
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.current_round = 0 if self.me == 0 else 0.5 # Track rounds, 0.5 for second player's first move
        self.total_value_to_me = sum(counts[i] * values[i] for i in range(len(counts)))
        self.num_object_types = len(counts)
        self.last_offer_value = 0 # To store the value of the last offer made by me

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
        
        # Sort items by value per item (descending).
        # If values are equal, prioritize items that we have more of (descending counts).
        # This helps in forming more 'complete' offers for highly valued items.
        item_priorities = sorted(
            [ (self.values[i], self.counts[i], i) for i in range(self.num_object_types) ],
            key=lambda x: (x[0], x[1]),
            reverse=True
        )

        remaining_items = self.counts.copy()

        # First pass: try to get desired items up to their available count
        for value_per_item, total_count, item_idx in item_priorities:
            if value_per_item > 0: # Only consider valuable items first
                num_to_take = min(remaining_items[item_idx], (target_value - current_value) // value_per_item)
                
                if num_to_take < 0: # Ensure we don't try to take negative items
                    num_to_take = 0

                my_offer[item_idx] += num_to_take
                current_value += num_to_take * value_per_item
                remaining_items[item_idx] -= num_to_take
            
            # If we've reached or exceeded our target, we can stop taking valuable items
            if current_value >= target_value:
                break
        
        # If after prioritizing valuable items, we still haven't met our target,
        # or we want to push for a higher value if we haven't offered much recently
        # or in early rounds, take more until we reach target or run out of valuable items.
        if current_value < target_value:
            for value_per_item, total_count, item_idx in item_priorities:
                if value_per_item > 0:
                    while remaining_items[item_idx] > 0 and current_value < target_value:
                        my_offer[item_idx] += 1
                        current_value += value_per_item
                        remaining_items[item_idx] -= 1
        
        # Ensure that items with zero value to us are not taken if possible,
        # unless necessary to complete an offer (though this logic prioritizes valuable items first).
        # Distribute remaining items (worthless to me, or if my desired value is very low) to the partner
        # We ensure all items are distributed, any not explicitly taken by us are implicitly for the partner.
        
        # However, the framework requires us to return what *we* want. So, let's make sure
        # our offer doesn't exceed available counts.
        for i in range(self.num_object_types):
            if my_offer[i] > self.counts[i]:
                my_offer[i] = self.counts[i]

        return my_offer

    def offer(self, o: list[int] | None) -> list[int] | None:
        if self.me == 0:
            if o is not None:
                self.current_round += 1
        else: # me == 1
            self.current_round += 0.5 # My turns are 0.5, 1.5, 2.5...
            if o is not None:
                self.current_round += 0.5 # Once partner makes an offer our current_round (internal for agent) reflects the round just played

        total_possible_turns = self.max_rounds * 2 
        
        # Dynamic strategy for demand percentage
        # Start high, decrease over time.
        # Use a non-linear decay to be more stubborn initially and more flexible towards the end.
        progress_ratio = self.current_round / self.max_rounds
        
        # Polynomial decay: start high, drop slowly, then faster towards the end
        initial_min_val_percentage = 0.98 if self.total_value_to_me > 0 else 0.0 # Start very high for valuable items
        final_min_val_percentage = 0.51 # Aim for slightly above 50% to prevent being undercut

        # Adjust minimum acceptance/demand based on progress.
        # Using a cosine decay for smoother and less drastic changes in early rounds.
        if self.max_rounds > 0:
            # Scale progress_ratio to [0, pi/2] for cosine, so cos(0)=1, cos(pi/2)=0
            decay_factor = math.cos(0.5 * math.pi * min(progress_ratio, 1.0))
            my_required_percentage = final_min_val_percentage + (initial_min_val_percentage - final_min_val_percentage) * decay_factor
        else:
            my_required_percentage = initial_min_val_percentage

        # Ensure we always demand at least a fair share, especially if total_value is very low (e.g., all 0s)
        if self.total_value_to_me == 0:
            my_required_percentage = 0.0
        else:
            # If the calculated percentage would result in 0 value, but we have items, set a minimum non-zero percentage
            if self.total_value_to_me * my_required_percentage < 1 and self.total_value_to_me > 0:
                my_required_percentage = max(my_required_percentage, 1 / self.total_value_to_me)


        # If it's the opponent's "last word" round, I should be more aggressive or ensure a deal
        is_opponent_last_turn = ( (self.me == 0 and self.current_round == self.max_rounds - 0.5) or
                                  (self.me == 1 and self.current_round == self.max_rounds - 0) ) 
        
        # If it's my "last word" round, ensure a deal by being flexible
        is_my_last_turn_to_make_offer = ( (self.me == 0 and self.current_round >= self.max_rounds - 0.5) or
                                         (self.me == 1 and self.current_round >= self.max_rounds - 0) )

        if o is not None:
            # Evaluate partner's offer
            offer_value = self.calculate_value(o)
            
            # Acceptance condition:
            # 1. Offer meets or exceeds my current required percentage.
            # 2. It's the very last negotiation turn and the offer is positive,
            #    or if my required percentage is very low (meaning I am desperate for a deal)
            #    and the offer is at least a minimum threshold (e.g., more than nothing).
            if offer_value >= self.total_value_to_me * my_required_percentage:
                return None  # Accept offer
            
            # Special case for last turn acceptance: If the opponent's offer gives me *any* value, accept it
            # if it's the absolute final offer.
            if is_my_last_turn_to_make_offer and offer_value > 0:
                 return None

            # If I am going to make an offer, store the value of their rejected offer to inform my next offer strategy
            self.last_offer_value = offer_value

        # Counter-offer logic or initial offer
        my_offer_percentage = my_required_percentage

        # If it's the last possible round and I haven't accepted, I must make a final effort.
        # This means offering a percentage that slightly favors myself but is close to fair,
        # or accepting any non-zero offer if given the chance.
        if is_my_last_turn_to_make_offer:
            # On the absolute last turn, be more flexible to ensure a deal instead of no deal.
            # Try to aim for slightly above 50% but not too aggressively.
            my_offer_percentage = max(my_required_percentage, 0.51)

        # Create the offer based on the calculated percentage
        my_new_offer = self.create_my_offer(my_offer_percentage)
        self.last_offer_value = self.calculate_value(my_new_offer) # Update last offer value for consistency

        return my_new_offer