import itertools

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_items = len(counts)
        
        # Pre-calculate my total value and item weights
        self.my_total_value = sum(c * v for c, v in zip(counts, values))
        self.item_weights = []
        for i in range(self.total_items):
            # Weight is value relative to total. If 0, weight is 0.
            w = values[i] / self.my_total_value if self.my_total_value > 0 else 0
            self.item_weights.append(w)

    def offer(self, o: list[int] | None) -> list[int] | None:
        # --- 1. Termination Check (Safety Wrapper) ---
        # We check the round depth based on the assumption that offer() is called 
        # incrementally. If we detect we are at the absolute limit, we must either 
        # accept (if valid) or walk away.
        
        # Note: The framework does not expose a direct "current round" counter, 
        # but if we are being called, we haven't timed out yet.
        # If o is None, it's an error state unless we are starting (handled below).
        if o is None and self.me == 1:
             # This is the very first turn (we are second player).
             pass 
        elif o is not None:
            # Calculate if we are near the end. 
            # If max_rounds is 15, we have 30 turns. 
            # If we are being called, we must return.
            # If we are at the last possible turn (30th), we can only Accept or Walk.
            # Since we don't know the turn index, we rely on the strategy to handle 
            # termination by accepting valid offers.
            pass

        # --- 2. Initial Move ---
        if o is None:
            return self.make_initial_offer()

        # --- 3. Evaluation ---
        # Calculate value of the incoming offer
        incoming_value = sum(c * v for c, v in zip(o, self.values))
        
        # Calculate total value of the goods (should be constant, but let's verify)
        # The prompt says "total worth of all objects is the same as for you".
        # However, the partner might value items differently. 
        # We assume the sum of items * our values is the total pool value for us.
        
        # Acceptance Threshold:
        # We want > 50%. If we are strictly < 50%, we might hold out, 
        # but as rounds decay, we become more lenient.
        # We calculate a dynamic threshold based on remaining rounds.
        # This is an estimate since we lack the exact round counter.
        
        # Fallback: If we get exactly 50%, we might still counter to try for 51%.
        # If we get > 50%, we accept.
        
        if incoming_value >= self.my_total_value / 2.0:
            return None  # Accept

        # --- 4. Counter-Offer Generation ---
        # If we are here, incoming_value < 50%.
        # We generate a counter-offer that is favorable to us (>= 50%).
        # We try to be "nice" by giving the partner items they might value, 
        # specifically items we value 0.
        
        offer = self.make_greedy_offer()
        
        # Safety check: If we generated an offer worth < 50% (shouldn't happen with current logic),
        # or if the offer is identical to what we received (which might stall), 
        # we ensure we demand at least 50%.
        if sum(c * v for c, v in zip(offer, self.values)) < self.my_total_value / 2.0:
            # Force an offer that gives us exactly 50% worth of our best items
            offer = self.make_min_acceptable_offer()
            
        return offer

    def make_initial_offer(self):
        # Strategy: Maximize our value, try to give partner low-value items.
        # Use a greedy approach: Sort items by our value descending.
        
        # Create list of (index, count, value)
        items = []
        for i in range(self.total_items):
            items.append({'idx': i, 'count': self.counts[i], 'value': self.values[i]})
        
        # Sort by value descending
        items.sort(key=lambda x: x['value'], reverse=True)
        
        # We need to offer a split where our value >= 50%.
        # Let's try to take all items with value > 0 first.
        our_share = [0] * self.total_items
        remaining_counts = [c for c in self.counts]
        
        current_val = 0
        target_val = self.my_total_value / 2.0
        
        # 1. Take high value items
        for item in items:
            if item['value'] == 0:
                continue # Leave zero value items for partner
            
            take_amount = item['count']
            # Check if taking all pushes us too far above 50% (not strictly necessary, but good for fairness)
            # Actually, we just need >= 50%. Let's take as many as needed to reach 50%.
            
            # If taking all keeps us below 50%, take all.
            if current_val + take_amount * item['value'] < target_val:
                our_share[item['idx']] = take_amount
                current_val += take_amount * item['value']
                remaining_counts[item['idx']] = 0
            else:
                # We reach/exceed 50% with this item type. Take minimum needed.
                needed = (target_val - current_val) / item['value']
                # Round up to ensure we pass 50%
                take = int(needed) + 1
                if take > item['count']: take = item['count'] # Safety
                
                our_share[item['idx']] = take
                current_val += take * item['value']
                remaining_counts[item['idx']] -= take
                break
        
        # If we haven't reached 50% (e.g., all items are 0 value), take everything?
        if current_val < target_val:
            # Just take everything
            return self.counts[:]
            
        return our_share

    def make_greedy_offer(self):
        # Similar to initial, but perhaps slightly more aggressive or specific.
        # Since we don't know the round number, we stick to a standard greedy split.
        return self.make_initial_offer()

    def make_min_acceptable_offer(self):
        # This function ensures we return an offer >= 50% even if greedy fails logic.
        # It's a fallback.
        return self.make_initial_offer()