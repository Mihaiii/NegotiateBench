from typing import List, Optional
import itertools

class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        
        # Calculate total value and item indices sorted by our value (descending)
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.item_count = len(counts)
        
        # Generate item indices sorted by value-to-count ratio (efficiency)
        self.item_priorities = sorted(
            range(self.item_count), 
            key=lambda i: (values[i], -counts[i]), 
            reverse=True
        )
        
        # Track negotiation state
        self.round = 0
        self.turn = 0
        self.best_opponent_offer = None
        self.best_opponent_value = 0
        self.opponent_concession_rate = 1.0
        self.my_last_offer = None
        
        # Strategic parameters (tuned based on observed behavior)
        self.reservation_value = self.total_value * 0.5  # Never accept below this
        self.initial_target = self.total_value * 0.85   # Start high
        self.final_target = self.total_value * 0.6      # Be willing to settle here
        
        # Generate a Pareto-efficient frontier of allocations
        self.frontier = self._generate_frontier()
        
    def _generate_frontier(self) -> List[List[int]]:
        """Generate a set of Pareto-efficient allocations"""
        allocations = []
        
        # First, get the allocation that maximizes our value
        max_alloc = []
        for i in range(self.item_count):
            if self.values[i] > 0:
                max_alloc.append(self.counts[i])
            else:
                max_alloc.append(0)
        
        allocations.append((self._calculate_value(max_alloc), max_alloc))
        
        # Generate key compromise allocations by giving up low-value items first
        for items_to_keep in range(len(self.item_priorities), 0, -1):
            alloc = [0] * self.item_count
            for idx in self.item_priorities[:items_to_keep]:
                alloc[idx] = self.counts[idx]
            value = self._calculate_value(alloc)
            if value >= self.reservation_value:
                allocations.append((value, alloc))
        
        # Add some balanced allocations
        for i in range(3):
            alloc = [0] * self.item_count
            for idx in self.item_priorities:
                # Keep some fraction of high-value items
                if self.values[idx] > 0:
                    keep_fraction = max(0.5 - i * 0.15, 0.2)
                    alloc[idx] = int(self.counts[idx] * keep_fraction)
            if self._calculate_value(alloc) >= self.reservation_value:
                allocations.append((self._calculate_value(alloc), alloc))
        
        # Sort by value descending
        allocations.sort(key=lambda x: x[0], reverse=True)
        return [alloc for _, alloc in allocations]
    
    def _calculate_value(self, allocation: List[int]) -> int:
        """Calculate value of an allocation"""
        return sum(v * a for v, a in zip(self.values, allocation))
    
    def _is_better_offer(self, offer1: List[int], offer2: List[int]) -> bool:
        """Return True if offer1 gives us more value than offer2"""
        return self._calculate_value(offer1) > self._calculate_value(offer2)
    
    def _generate_counter_offer(self, target_value: float) -> List[int]:
        """Generate a counter-offer aiming for target_value"""
        # Try to find an allocation in frontier close to target
        best_alloc = None
        best_diff = float('inf')
        
        for alloc in self.frontier:
            value = self._calculate_value(alloc)
            diff = abs(value - target_value)
            if diff < best_diff:
                best_diff = diff
                best_alloc = alloc
        
        # If no good allocation, create one by keeping high-value items
        if best_alloc is None:
            alloc = [0] * self.item_count
            remaining_value = target_value
            for idx in self.item_priorities:
                if remaining_value <= 0:
                    break
                item_value = self.values[idx]
                if item_value > 0:
                    max_items = self.counts[idx]
                    # Take as many as needed to reach target
                    items_needed = min(max_items, int(remaining_value / item_value))
                    alloc[idx] = items_needed
                    remaining_value -= items_needed * item_value
            best_alloc = alloc
        
        return best_alloc
    
    def _analyze_opponent_behavior(self, current_offer: Optional[List[int]]) -> None:
        """Analyze opponent's offers to adjust strategy"""
        if current_offer is None:
            return
            
        current_value = self._calculate_value(current_offer)
        
        # Track best offer from opponent
        if current_value > self.best_opponent_value:
            self.best_opponent_value = current_value
            self.best_opponent_offer = current_offer
        
        # Estimate opponent concession rate (only if we have history)
        if self.my_last_offer:
            # Calculate what opponent is giving us compared to what we asked for
            my_last_value = self._calculate_value(self.my_last_offer)
            if my_last_value > 0:
                concession = current_value / my_last_value
                self.opponent_concession_rate = min(
                    self.opponent_concession_rate,
                    concession
                )
    
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        """Make or accept an offer"""
        self.turn += 1
        self.round = (self.turn + 1) // 2
        
        # Analyze opponent's offer
        self._analyze_opponent_behavior(o)
        
        # Calculate progress through negotiation (0 to 1)
        total_turns = self.max_rounds * 2
        progress = self.turn / total_turns if total_turns > 0 else 0
        
        # Dynamically adjust target based on progress and opponent behavior
        if progress < 0.3:
            # Early game: aggressive
            target_ratio = 0.85 - (progress * 0.25)
        elif progress < 0.7:
            # Middle game: moderate
            target_ratio = 0.70 - ((progress - 0.3) * 0.25)
        else:
            # End game: flexible but maintain minimum
            target_ratio = max(0.55, 0.60 - ((progress - 0.7) * 0.3))
        
        # Adjust for opponent behavior - if they're tough, be more flexible
        if self.opponent_concession_rate < 0.7 and progress > 0.5:
            target_ratio *= 0.9
        
        current_target = self.total_value * target_ratio
        
        # Always accept if opponent offers at least our current target
        if o is not None:
            offer_value = self._calculate_value(o)
            if offer_value >= current_target:
                return None
            
            # Special case: if opponent repeats same good offer, consider accepting
            if (offer_value >= self.reservation_value * 1.2 and 
                self.turn > total_turns * 0.7 and
                self._calculate_value(o) >= self.best_opponent_value * 0.95):
                return None
        
        # Last turn logic - be very flexible to avoid no-deal
        if self.turn >= total_turns - 1:
            if o is not None and self._calculate_value(o) > 0:
                # Accept any positive offer on last turn if we're responding
                if self.me == (self.turn % 2):  # We're responding on last turn
                    return None
                else:
                    # We're making last offer - make a very generous one
                    final_offer = self._generate_counter_offer(self.reservation_value * 1.1)
                    self.my_last_offer = final_offer
                    return final_offer
        
        # Generate counter-offer
        counter_offer = self._generate_counter_offer(current_target)
        self.my_last_offer = counter_offer
        
        # If opponent's last offer was close to our counter, consider accepting theirs
        if (o is not None and self.turn > 2 and 
            abs(self._calculate_value(o) - self._calculate_value(counter_offer)) < 
            self.total_value * 0.05):
            # Our counter is very similar to their offer - accept to close deal
            return None
        
        return counter_offer