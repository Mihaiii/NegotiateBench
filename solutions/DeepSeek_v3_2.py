import itertools
import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.turn = 0  # Track turns instead of rounds
        
        # Calculate total value for us
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Sort items by value (descending)
        self.item_indices = list(range(len(counts)))
        self.item_indices.sort(key=lambda i: values[i], reverse=True)
        
        # Pre-compute all possible splits for faster evaluation
        self.all_splits = self._generate_all_splits()
        
        # Track negotiation state
        self.opponent_offers = []
        self.my_offers = []
        self.min_acceptable = self.total_value * 0.4  # Minimum we'll accept
        
        # For opponent modeling
        self.opponent_preferences = [0] * len(counts)
        
        # Generate initial aspiration offer
        self.aspiration_offer = self._get_aspiration_offer()
        
        # For concession strategy
        self.concession_factor = 1.0
        self.rounds_left = max_rounds
        
    def _generate_all_splits(self):
        """Generate all possible allocations for each item type."""
        splits_by_item = []
        for count in self.counts:
            item_splits = [(i, count - i) for i in range(count + 1)]
            splits_by_item.append(item_splits)
        
        # Generate all combinations
        all_combinations = list(itertools.product(*splits_by_item))
        
        # Convert to our perspective (what we get)
        result = []
        for combo in all_combinations:
            our_share = [c[0] for c in combo]
            result.append(our_share)
        return result
    
    def _get_aspiration_offer(self):
        """Get our initial high aspiration offer."""
        offer = [0] * len(self.counts)
        # Take everything we value positively
        for i in self.item_indices:
            if self.values[i] > 0:
                offer[i] = self.counts[i]
        return offer
    
    def _evaluate_offer(self, offer):
        """Evaluate an offer from our perspective."""
        return sum(v * c for v, c in zip(self.values, offer))
    
    def _is_valid_offer(self, offer):
        """Check if an offer is valid (doesn't exceed counts)."""
        return all(0 <= c <= total for c, total in zip(offer, self.counts))
    
    def _update_opponent_model(self, offer):
        """Update our model of opponent's preferences."""
        if not self.opponent_offers:
            return
        
        # Compare with previous offers to infer preferences
        if len(self.opponent_offers) > 1:
            last_offer = self.opponent_offers[-1]
            for i in range(len(offer)):
                if offer[i] < last_offer[i]:
                    # They're keeping more of this item
                    self.opponent_preferences[i] += 1
                elif offer[i] > last_offer[i]:
                    # They're giving more of this item
                    self.opponent_preferences[i] -= 1
    
    def _generate_counter_offer(self, opponent_offer=None):
        """Generate a counter-offer based on current state."""
        self.turn += 1
        rounds_passed = self.turn / 2  # Each turn is 0.5 rounds
        
        # Calculate time pressure (0 at start, 1 at end)
        time_pressure = min(1.0, rounds_passed / self.max_rounds)
        
        # Adjust minimum acceptable based on time pressure
        # Start high, decrease gradually
        current_min = self.total_value * (0.7 - 0.4 * time_pressure)
        self.min_acceptable = max(self.total_value * 0.3, current_min)
        
        # If we have opponent offers, try to infer win-win splits
        best_offer = None
        best_value = -1
        
        if opponent_offer is not None:
            # Try to find Pareto improvements over opponent's last offer
            opponent_value_to_us = self._evaluate_offer(opponent_offer)
            
            for offer in self.all_splits:
                our_value = self._evaluate_offer(offer)
                
                # Must be better than minimum acceptable
                if our_value < self.min_acceptable:
                    continue
                
                # Try to find offers that are Pareto improvements
                # We assume opponent values items we don't value
                estimated_opponent_value = 0
                for i in range(len(offer)):
                    if self.values[i] == 0:  # We don't value this
                        # Assume opponent might value it
                        estimated_opponent_value += (self.counts[i] - offer[i]) * 2
                
                # Score based on our value and estimated opponent value
                score = our_value + estimated_opponent_value * 0.5
                
                if score > best_value:
                    best_value = score
                    best_offer = offer
        
        # If no good offer found or no opponent offer, use concession strategy
        if best_offer is None:
            best_offer = self._concession_strategy(time_pressure)
        
        self.my_offers.append(best_offer)
        return best_offer
    
    def _concession_strategy(self, time_pressure):
        """Generate offer based on concession strategy."""
        offer = [0] * len(self.counts)
        
        # Determine how much to concede based on time pressure
        target_value = self.total_value * (0.9 - 0.6 * time_pressure)
        
        # Start with everything we value
        for i in self.item_indices:
            if self.values[i] > 0:
                offer[i] = self.counts[i]
        
        current_value = self._evaluate_offer(offer)
        
        # If we need to concede
        if current_value > target_value:
            excess = current_value - target_value
            
            # Concede from least valuable items first
            for i in reversed(self.item_indices):
                if offer[i] > 0 and self.values[i] > 0:
                    # Calculate how many to give up
                    items_to_give = min(offer[i], int(excess / self.values[i] + 0.5))
                    if items_to_give > 0:
                        offer[i] -= items_to_give
                        excess -= items_to_give * self.values[i]
                
                if excess <= 0:
                    break
        
        # Ensure we never give up everything
        min_items = max(1, int(len([v for v in self.values if v > 0]) * 0.3))
        valuable_items = [i for i in self.item_indices if self.values[i] > 0]
        
        if len(valuable_items) > 0:
            # Keep at least some of our top valuable items
            for i in valuable_items[:min_items]:
                if offer[i] == 0:
                    offer[i] = min(1, self.counts[i])
        
        return offer
    
    def _should_accept(self, offer):
        """Determine if we should accept an offer."""
        if offer is None:
            return False
            
        our_value = self._evaluate_offer(offer)
        
        # Calculate time-based acceptance threshold
        time_factor = min(1.0, self.turn / (self.max_rounds * 2))
        
        # Threshold decreases over time but has a floor
        threshold = max(
            self.min_acceptable,
            self.total_value * (0.6 - 0.3 * time_factor)
        )
        
        # Also consider if it's the last round
        is_last_chance = (self.turn >= self.max_rounds * 2 - 1)
        
        if is_last_chance:
            # In last chance, accept if it's better than walking away
            return our_value >= self.total_value * 0.3
        
        return our_value >= threshold
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        # Track opponent's offer if provided
        if o is not None:
            if self._is_valid_offer(o):
                self.opponent_offers.append(o)
                self._update_opponent_model(o)
            
            # Check if we should accept
            if self._should_accept(o):
                return None
        
        # Check if we're in the last round and should be more flexible
        if self.turn >= self.max_rounds * 2 - 1 and o is not None:
            # Last chance to make a deal
            our_value = self._evaluate_offer(o)
            if our_value >= self.total_value * 0.3:  # Bare minimum
                return None
        
        # Generate and return counter-offer
        counter_offer = self._generate_counter_offer(o)
        
        # Ensure the counter-offer is valid
        if not self._is_valid_offer(counter_offer):
            # Fallback to a safe offer
            counter_offer = self.aspiration_offer.copy()
        
        return counter_offer