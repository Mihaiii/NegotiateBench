import itertools

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.rounds_left = max_rounds
        
        # Calculate total potential value (upper bound)
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Pre-generate all possible deals (partitions) from 'my' perspective.
        # A deal is defined by the count of items I receive.
        # We store: (my_value, opponent_item_count, partition_list)
        self.possible_deals = []
        
        # Creating ranges for itertools product (0 to count for each item type)
        ranges = [range(c + 1) for c in counts]
        
        for partition in itertools.product(*ranges):
            partition = list(partition)
            
            # Calculate my utility for this partition
            my_val = sum(p * v for p, v in zip(partition, values))
            
            # Calculate the number of items the opponent gets (Generosity Heuristic)
            # We assume opponents prefer getting more physical items if values are unknown.
            opp_items_count = sum((counts[i] - partition[i]) for i in range(len(counts)))
            
            self.possible_deals.append({
                "partition": partition,
                "value": my_val,
                "opp_items": opp_items_count
            })
            
        # Sort deals primarily by My Value (Descending), 
        # and secondarily by Opponent Item Count (Descending).
        # This helps us pick the "nicest" high-value offer later.
        self.possible_deals.sort(key=lambda x: (x["value"], x["opp_items"]), reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Determine current 'time' in the negotiation (0.0 start -> 1.0 end)
        # We use rounds_left to estimate urgency.
        progress = (self.max_rounds - self.rounds_left) / float(self.max_rounds)

        # 1. Analyze Incoming Offer
        offer_value = -1
        if o is not None:
            offer_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # END-GAME LOGIC (Second Player)
            # If I am Player 1 and this is the last round (Turn 2*max_rounds),
            # rejecting means we both get 0. I must accept anything > 0.
            if self.me == 1 and self.rounds_left == 1:
                if offer_value > 0 or self.total_value == 0:
                    return None

        # 2. Calculate Dynamic Threshold (Boulware Strategy)
        # We want to start high and concede slowly, dropping to a reservation price at the end.
        
        # Reservation price: roughly 60% of total value (aim for slightly better than even).
        min_frac = 0.6
        
        # END-GAME LOGIC (First Player)
        # If I am Player 0 and this is the last round, this is my LAST offer.
        # I must offer something the opponent is very likely to accept (~50-55%).
        if self.me == 0 and self.rounds_left == 1:
            min_frac = 0.55
            
        # Curve: Total * (1 - (1-min) * progress^3)
        # The power of 3 keeps the required value high for the first ~70% of the game.
        current_threshold = self.total_value * (1.0 - (1.0 - min_frac) * (progress ** 3))
        
        # 3. Decision: Accept?
        if o is not None:
            # If the offer is good enough, take it.
            if offer_value >= current_threshold:
                self.rounds_left -= 1
                return None

        # 4. Decision: Counter-Offer
        # We look for the best deal for ME that is just above my concession threshold.
        # Using a deal closer to the threshold increases the chance the opponent accepts
        # (because it likely gives them more value than my greedy top offers).
        
        # Filter deals that pass the threshold
        candidates = [d for d in self.possible_deals if d["value"] >= current_threshold]
        
        if not candidates:
            # Fallback (shouldn't happen unless threshold > total): Demand everything
            best_offer = self.possible_deals[0]["partition"]
        else:
            # 'candidates' is sorted by Value Descending.
            # The deals at the END of 'candidates' are the ones closest to the threshold.
            # Strategy: Pick the deal with the LOWEST value that satisfies the threshold
            # to maximize opponent appeal (Conceder behavior at the offer level).
            
            # Find the value of the last candidate (closest to threshold)
            target_val = candidates[-1]["value"]
            
            # Get all deals with this specific value
            # (There might be multiple ways to get the same score)
            ties = [d for d in candidates if d["value"] == target_val]
            
            # Among ties, pick the one that gives the MOST items to the opponent.
            # Our sort order (Opp Items Desc) ensures the first one in 'ties' logic needs care.
            # Actually, the main sort was (Value DESC, OppItems DESC).
            # So within a value bracket, the one with MOST opp items is FIRST.
            best_offer = ties[0]["partition"]

        # Decrement counter for next call
        self.rounds_left -= 1
        
        return best_offer