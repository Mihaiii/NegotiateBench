import itertools

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.rounds_left = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))

        # 1. Generate all possible partitions of items I can receive.
        # Create ranges for each item type: [0, 1, ... count].
        ranges = [range(c + 1) for c in counts]
        all_bundles = []
        
        # Calculate value for every permutation of items.
        for bundle in itertools.product(*ranges):
            val = sum(q * v for q, v in zip(bundle, values))
            # Store tuple: (my_value, total_item_count, bundle_list)
            all_bundles.append((val, sum(bundle), list(bundle)))

        # 2. Sort bundles to prioritize my gain.
        # Primary Key: My Value (High to Low).
        # Secondary Key: Total Items I Take (Low to High). 
        # Heuristic: If value is equal, taking fewer items leaves more for the opponent,
        # increasing the probability they find utility in the remainder.
        # Note: In Python sort, True > False. We construct key so Descending sort works for both logic.
        # But simple lambda with reverse=True: (Value, -ItemCount)
        # Higher value comes first. For ties, less negative ItemCount (smaller count) comes first? 
        # No, -2 > -5. So (10, 2) comes before (10, 5).
        all_bundles.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        self.sorted_bundles = all_bundles

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Calculate how much time has passed (0.0 to 1.0)
        # If rounds_left = max, progress = 0. If rounds_left = 1, progress = 1.
        progress = (self.max_rounds - self.rounds_left) / max(1, self.max_rounds - 1) if self.max_rounds > 1 else 1.0
        
        # Concession Strategy:
        # Define the range of acceptable values based on time.
        max_val = self.sorted_bundles[0][0]
        reservation_val = int(self.total_value / 2) # We aim for at least half
        
        # Calculate current aspiration level (Linear concession)
        current_threshold = max_val - (max_val - reservation_val) * progress

        # 1. Evaluate Opponent's Offer (if exists)
        if o is not None:
            offer_value = sum(q * v for q, v in zip(o, self.values))
            
            # Acceptance Logic:
            # A. Offer meets our current strategic threshold
            if offer_value >= current_threshold:
                self.rounds_left -= 1
                return None
            
            # B. "Last Chance" Logic
            # If I am the second player (me=1) and this is the last round,
            # rejecting implies making a counter-offer which ends the game with no agreement.
            # Therefore, we must accept any offer that provides a baseline fair value.
            if self.me == 1 and self.rounds_left == 1:
                if offer_value >= reservation_val:
                    self.rounds_left -= 1
                    return None

        # 2. Formulate Counter-Offer
        # Filter bundles that meet the current threshold.
        candidates = [b for b in self.sorted_bundles if b[0] >= current_threshold]
        
        if not candidates:
            # Fallback to max value if threshold calculation drifts (unlikely)
            best_bundle = self.sorted_bundles[0][2]
        else:
            # Strategy: To maximize agreement probability while respecting threshold,
            # we choose the offers closest to the threshold (most generous to opponent 
            # while still allowed by our current concession level).
            
            # The list is sorted High Value -> Low Value.
            # The candidates at the end of the list are close to current_threshold.
            target_val = candidates[-1][0]
            
            # Get all bundles providing exactly this value
            best_deals_at_val = [b for b in candidates if b[0] == target_val]
            
            # Tie-breaker: Choose the one where we take the FEWEST physical items 
            # (leaving max items for opponent).
            best_bundle = min(best_deals_at_val, key=lambda x: x[1])[2]

        self.rounds_left -= 1
        return best_bundle