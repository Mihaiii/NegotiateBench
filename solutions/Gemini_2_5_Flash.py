import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me  # 0 if I go first, 1 if I go second
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        # current_round is 0-indexed for full rounds completed.
        # If me=0, offers at 0, 1, 2... max_rounds-1
        # If me=1, offers at 0.5, 1.5, 2.5... max_rounds-0.5
        self.current_round_num = 0.0 # Represents the start of the current round I'm in
        self.total_value_to_me = sum(counts[i] * values[i] for i in range(len(counts)))
        self.num_object_types = len(counts)

    def calculate_value(self, offer_items: list[int]) -> int:
        """Calculates the value of a given offer for me."""
        return sum(self.values[i] * offer_items[i] for i in range(self.num_object_types))

    def create_my_offer(self, target_percentage: float) -> list[int]:
        """
        Creates an offer for myself aiming for a certain percentage of the total value.
        It prioritizes getting more valuable items first while respecting counts.
        """
        target_value = int(self.total_value_to_me * target_percentage)
        my_offer = [0] * self.num_object_types
        current_value = 0
        
        # Sort items by value per unit (descending) and then by count (descending)
        # This means we try to get the most valuable items first.
        item_priorities = sorted(
            [ (self.values[i], self.counts[i], i) for i in range(self.num_object_types) ],
            key=lambda x: (x[0], x[1]),
            reverse=True
        )

        remaining_counts = self.counts.copy()

        # First pass: try to acquire items up to the target value
        for value_per_item, total_count, item_idx in item_priorities:
            if current_value >= target_value:
                break # Reached or exceeded target value

            if value_per_item > 0:
                # How many of this item can we take without exceeding total count or target value?
                can_take = remaining_counts[item_idx]
                needed_to_reach_target = math.ceil((target_value - current_value) / value_per_item)
                
                num_to_take = min(can_take, needed_to_reach_target)
                
                if num_to_take > 0:
                    my_offer[item_idx] += num_to_take
                    current_value += num_to_take * value_per_item
                    remaining_counts[item_idx] -= num_to_take

        # Fallback for target_value = 0 or if all valuable items are taken and value is still low.
        # This ensures we always try to make a complete offer.
        # If we couldn't reach the target value with valuable items, or if our target was 0,
        # we can distribute the remaining items (mostly worthless to us, or just small value ones).
        # However, the primary goal of this method is to get *my_offer* to a certain value.
        # It's not about what the partner gets, but what I demand.
        # The current implementation correctly focuses on maximizing my value up to the target.
        
        return my_offer

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Update current round number.
        # If me=0 (first player), my turns are 0, 1, 2...
        # If me=1 (second player), my turns are 0.5, 1.5, 2.5...
        # This calculation ensures current_round_num correctly reflects the conceptual round.
        if o is None: # My first move
            if self.me == 1: # Second player's first move
                self.current_round_num = 0.5
            # If me == 0, current_round_num is already 0.0
        else: # Opponent made an offer, so a full turn has passed
            self.current_round_num += 1.0


        # Calculate negotiation progress (0.0 to 1.0)
        # We need to be careful with max_rounds, as it can be 0 for final offer scenarios.
        if self.max_rounds > 0:
            # max_rounds is total rounds, but turn numbers go up to max_rounds - 0.5 or max_rounds - 1
            # A turn is over when I either accept or make a counter-offer.
            # My current_round_num can go up to max_rounds - 0.5 (if me=1, last turn) or max_rounds - 1 (if me=0, last turn)
            effective_rounds = self.max_rounds # Max full rounds
            progress = min(self.current_round_num / effective_rounds, 1.0)
        else:
            progress = 1.0 # If max_rounds is 0, we are at the very end

        # Dynamic demand percentage: start high, decrease over time.
        # Use a non-linear decay to be more stubborn initially and more flexible towards the end.
        initial_demand_percentage = 1.0 # Start by demanding everything if sensible, or slightly less aggressively.
        final_demand_percentage = 0.51 # Aim for slightly above 50% to ensure a win

        if self.total_value_to_me == 0:
            # If all items are worthless to me, I have no preference.
            # I should accept any offer and offer nothing for myself.
            demand_percentage = 0.0
        else:
            # Adjust demand based on progress
            # Using a cubic decay for faster reduction towards the end
            # (1 - progress_x)^3 gives a high value for low progress_x, quickly drops as progress_x approaches 1.
            decay_factor = (1 - progress)**3 
            demand_percentage = final_demand_percentage + (initial_demand_percentage - final_demand_percentage) * decay_factor

        # Ensure demand doesn't exceed 100% or fall below a minimum
        demand_percentage = max(min(demand_percentage, 1.0), 0.0)


        # Check if it's the last possible *offer* I can make before the negotiations end.
        # My last chance to make an offer.
        # For me=0: current_round_num can be 0, 1, ..., max_rounds - 1. My last offer is when current_round_num = max_rounds - 1.
        # For me=1: current_round_num can be 0.5, 1.5, ..., max_rounds - 0.5. My last offer is when current_round_num = max_rounds - 0.5.
        
        # Consider `max_rounds` to represent the number of *full* rounds (2 turns).
        # The total turns available are `2 * max_rounds`.
        # My turn number (0-indexed start): `round_idx = int(self.current_round_num)`
        # If me=0, my turns are 0, 1, ..., max_rounds-1
        # If me=1, my turns are 0.5, 1.5, ..., max_rounds-0.5
        # The overall turn number (0-indexed):
        # - My first turn (me=0): 0
        # - Partner's first turn (me=0): 1
        # - My second turn (me=0): 2
        # - ...
        # - My first turn (me=1): 1
        # - Partner's turn (me=1): 2
        # - My second turn (me=1): 3
        
        my_current_turn_index = -1
        if self.me == 0:
            my_current_turn_index = int(self.current_round_num * 2) # 0, 2, 4,...
        else: # self.me == 1
            my_current_turn_index = int(self.current_round_num * 2) # 1, 3, 5,...
            
        is_my_last_opportunity_to_make_offer = (my_current_turn_index == (2 * self.max_rounds - 2) if self.me == 0 else (2 * self.max_rounds - 1))
        
        # If an offer was made to me:
        if o is not None:
            offer_value = self.calculate_value(o)
            
            # Acceptance condition:
            # 1. Offer meets or exceeds my current calculated demand percentage.
            # 2. It's the absolute last turn for *any* agreement (which means `o` is the final counter-offer
            #    and I must decide to accept or walk away) and the offer is something.
            
            # The *very last turn* of the entire negotiation (my opportunity to accept or reject the final counter-offer)
            # This is when my current_round_num corresponds to the final round, and I'm receiving an offer.
            is_absolute_last_opportunity_to_accept = False
            if self.me == 0 and self.current_round_num == self.max_rounds - 0.5: # Partner's last offer, I can accept
                is_absolute_last_opportunity_to_accept = True
            elif self.me == 1 and self.current_round_num == self.max_rounds: # Partner's last offer, I can accept
                is_absolute_last_opportunity_to_accept = True
                
            if offer_value >= self.total_value_to_me * demand_percentage:
                return None  # Accept offer
            elif is_absolute_last_opportunity_to_accept and offer_value > 0:
                # If it's the very last turn and negotiations would end with nothing,
                # accept any offer that gives me something.
                return None
            elif self.total_value_to_me == 0 and offer_value == 0:
                 # If everything is worthless to me, and partner offers me 0, I accept.
                 # This handles cases where my total_value is 0; I don't care what I get.
                 return None

        # Create counter-offer (or initial offer)
        my_offer_to_make = self.create_my_offer(demand_percentage)
        
        # If it's my last possible turn to make an offer, ensure it's a reasonable one
        # to maximize chances of acceptance, even if it means reducing my immediate demand.
        if is_my_last_opportunity_to_make_offer:
            # Be more flexible, aim for minimal gain to ensure a deal over no deal.
            # Offer slightly above 50% to maintain a positive negotiation stance.
            final_offer_percentage = max(demand_percentage, 0.51) # Ensure we still want at least more than half
            if self.total_value_to_me == 0: # If I don't value anything, just offer nothing for myself
                final_offer_percentage = 0.0
            my_offer_to_make = self.create_my_offer(final_offer_percentage)
            
        return my_offer_to_make