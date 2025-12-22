import itertools
import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.rounds_left = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Opponent modeling: Weighted popularity of items the opponent keeps.
        # Initialized with small epsilon to handle initial math safely.
        self.opp_kept_counts = [0.1] * len(counts) 
        
        # 1. Generate all possible partitions (bundles) for myself.
        # We store tuples of (MyValue, ItemCount, BundleList).
        self.sorted_bundles = []
        
        # Calculate state space size to decide between Exhaustive vs Random generation
        state_space_size = 1
        for c in counts:
            state_space_size *= (c + 1)
            
        ranges = [range(c + 1) for c in counts]
        
        # Threshold for switching to stochastic generation to prevent timeout on huge inputs
        if state_space_size <= 50000:
            for bundle in itertools.product(*ranges):
                self._add_bundle(bundle)
        else:
            # Random sampling for large state spaces
            seen = set()
            # Always include extreme cases
            self._add_bundle(tuple(counts)) # All
            self._add_bundle(tuple(0 for _ in counts)) # Nothing
            seen.add(tuple(counts))
            seen.add(tuple(0 for _ in counts))
            
            attempts = 0
            while len(self.sorted_bundles) < 10000 and attempts < 40000:
                attempts += 1
                bundle = tuple(random.randint(0, c) for c in counts)
                if bundle not in seen:
                    self._add_bundle(bundle)
                    seen.add(bundle)

        # 2. Sort bundles: 
        # Primary: My Value (High to Low).
        # Secondary: Total Items I take (Low to High).
        # Theory: If value is same, taking fewer items leaves more for the opponent, 
        # increasing potential utility for them (Pareto optimality guess).
        self.sorted_bundles.sort(key=lambda x: (x[0], -sum(x[1])), reverse=True)

    def _add_bundle(self, bundle):
        val = sum(q * v for q, v in zip(bundle, self.values))
        # Store: (Value, BundleTuple)
        self.sorted_bundles.append((val, bundle))

    def offer(self, o: list[int] | None) -> list[int] | None:
        # 1. Update Opponent Model and Handle Incoming Offer
        if o is not None:
            # Calculate what opponent *kept* for themselves
            opp_kept = [total - offer_amt for total, offer_amt in zip(self.counts, o)]
            
            # Update history: Accumulate frequency of items opponent desires
            for i, k in enumerate(opp_kept):
                self.opp_kept_counts[i] += k
            
            offer_val_to_me = sum(q * v for q, v in zip(o, self.values))
            
            # --- Last Turn Survival Logic ---
            # If I am Player 1 (Second Mover) and rounds_left == 1, this is the absolute final turn.
            # If I make a counter-offer, the game ends with No Agreement (0 value).
            # Therefore, I must accept ANY valid positive value (and arguably even 0 if that's all there is, 
            # effectively "walking away" math-wise, but maximizing V > 0 is better).
            if self.me == 1 and self.rounds_left == 1:
                if offer_val_to_me > 0 or (offer_val_to_me == 0 and self.total_value == 0):
                    return None
            
            # --- Standard Acceptance Logic ---
            threshold = self._get_threshold()
            if offer_val_to_me >= threshold:
                self.rounds_left -= 1
                return None

        # 2. Formulate Counter-Offer
        current_threshold = self._get_threshold()
        
        # Filter bundles that satisfy my current threshold requirements
        candidates = []
        # Since sorted_bundles is sorted by value desc, we can iterate until fail
        for val, bundle in self.sorted_bundles:
            if val >= current_threshold:
                candidates.append(bundle)
            else:
                break 
        
        # If threshold is too high for any bundle (unlikely unless threshold > total),
        # fallback to max demand.
        if not candidates:
            best_offer = list(self.counts)
        else:
            # Among "satisfactory" deals for ME, pick the one best for THEM.
            # Heuristic: Find bundle where items given to opponent match their historical demand "opp_kept_counts".
            
            best_offer = candidates[0]
            best_score = -1.0
            
            for bundle_me in candidates:
                # Calculate what opponent receives in this split
                items_for_opp = [total - mine for total, mine in zip(self.counts, bundle_me)]
                
                # Dot product of (ItemsForOpp * OpponentInterestWeight)
                score = sum(amt * weight for amt, weight in zip(items_for_opp, self.opp_kept_counts))
                
                if score > best_score:
                    best_score = score
                    best_offer = bundle_me

        self.rounds_left -= 1
        return list(best_offer)

    def _get_threshold(self) -> int:
        """
        Calculates the minimum value I am willing to accept at this point in time.
        Uses a concession curve that starts high and drops towards a fair split.
        """
        if self.max_rounds <= 1:
            progress = 1.0
        else:
            # progress goes from 0.0 (start) to 1.0 (start of last round)
            progress = (self.max_rounds - self.rounds_left) / (self.max_rounds - 1)
        
        # Clamp progress 0-1
        progress = max(0.0, min(1.0, progress))
        
        # Strategy:
        # Start: Ask for full Total Value ("Boulware" strategy anchor).
        # End: Settle for slightly above 50% (Reservation Value).
        # We don't want to go strictly to 50% too early to avoid exploitation, 
        # but in the last round, we want to ensure a deal.
        
        start_val = self.total_value
        # Reservation: 55% of total value, or half if total is small. 
        # Ensuring we don't accidentally ask for > total on integer math is handled by Logic.
        end_val = int(self.total_value * 0.55) 

        # Linear interpolation
        # More complex curves (e.g. cubic) can be used, but linear is robust for unknown opponents.
        current_req = start_val - (start_val - end_val) * progress
        
        return int(current_req)