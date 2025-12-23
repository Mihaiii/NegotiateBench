import math
import random
from typing import List, Optional

class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        
        # Calculate my total value
        self.total_value = sum(counts[i] * values[i] for i in range(len(counts)))
        
        # Track negotiation state
        self.round = 0
        self.opponent_offers = []
        self.my_offers = []
        
        # Calculate normalized values for sorting items
        self.item_priority = sorted(
            range(len(counts)),
            key=lambda i: (values[i], -counts[i]),  # Higher value, fewer items first
            reverse=True
        )
        
        # Generate a Pareto-optimal frontier of allocations
        self.generate_frontier()
        
        # Strategic parameters
        self.opening_aggressiveness = 0.9  # Start demanding 90% of value
        self.min_acceptance_ratio = 0.5    # Never accept less than 50%
        self.concession_rate = 0.85        # Base concession rate
        
        # Opponent modeling
        self.opponent_values_estimate = None
        self.opponent_preference_confidence = [0] * len(counts)
        
    def generate_frontier(self):
        """Generate a set of good allocations efficiently using a greedy approach"""
        self.frontier = []
        
        # Generate allocations by taking items in priority order
        for target_ratio in [0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5]:
            allocation = self.create_allocation_for_ratio(target_ratio)
            if allocation not in self.frontier:
                self.frontier.append(allocation)
        
        # Also generate allocations that give away items we don't value
        zero_value_allocation = [0] * len(self.counts)
        for i in range(len(self.counts)):
            if self.values[i] > 0:
                zero_value_allocation[i] = self.counts[i]
        if zero_value_allocation not in self.frontier:
            self.frontier.append(zero_value_allocation)
        
        # Sort frontier by my value (descending)
        self.frontier.sort(key=lambda a: self.value_of(a), reverse=True)
    
    def create_allocation_for_ratio(self, target_ratio: float) -> List[int]:
        """Create an allocation that gives me approximately target_ratio of my total value"""
        allocation = [0] * len(self.counts)
        current_value = 0
        target_value = self.total_value * target_ratio
        
        # Take items in priority order until we reach target
        for i in self.item_priority:
            if self.values[i] == 0:
                continue
                
            # Take as many of this item as needed
            max_to_take = self.counts[i]
            item_value = self.values[i]
            
            # How many can we take without exceeding target too much?
            if item_value > 0:
                needed = min(max_to_take, max(0, math.ceil((target_value - current_value) / item_value)))
                if needed > 0:
                    allocation[i] = needed
                    current_value += needed * item_value
        
        # If we're under target, add more items
        if current_value < target_value:
            for i in self.item_priority:
                if self.values[i] == 0:
                    continue
                    
                remaining = self.counts[i] - allocation[i]
                if remaining > 0:
                    can_add = min(remaining, math.ceil((target_value - current_value) / self.values[i]))
                    if can_add > 0:
                        allocation[i] += can_add
                        current_value += can_add * self.values[i]
        
        return allocation
    
    def value_of(self, allocation: List[int]) -> int:
        """Calculate my value for an allocation"""
        return sum(allocation[i] * self.values[i] for i in range(len(allocation)))
    
    def opponent_value_estimate(self, allocation: List[int]) -> float:
        """Estimate opponent's value for what they get"""
        if self.opponent_values_estimate:
            # Use learned opponent values
            opponent_allocation = [self.counts[i] - allocation[i] for i in range(len(allocation))]
            return sum(opponent_allocation[i] * self.opponent_values_estimate[i] 
                      for i in range(len(allocation)))
        else:
            # Default estimate: assume opponent values opposite of me
            # This is a conservative estimate
            opponent_allocation = [self.counts[i] - allocation[i] for i in range(len(allocation))]
            return sum(opponent_allocation[i] * (10 - self.values[i]) 
                      for i in range(len(allocation))) / 10.0
    
    def update_opponent_model(self, offer: List[int]):
        """Learn opponent's preferences from their offers"""
        # Their offer shows what they want me to have
        # Items they don't offer me, they likely want for themselves
        for i in range(len(offer)):
            if offer[i] == 0:
                # They're keeping all of this item
                self.opponent_preference_confidence[i] += 1
            elif offer[i] == self.counts[i]:
                # They're giving me all of this item
                self.opponent_preference_confidence[i] -= 1
        
        # After several offers, estimate opponent's values
        if len(self.opponent_offers) >= 3:
            self.estimate_opponent_values()
    
    def estimate_opponent_values(self):
        """Estimate opponent's values based on their offers"""
        self.opponent_values_estimate = [0] * len(self.counts)
        
        # Look for patterns in opponent's offers
        for i in range(len(self.counts)):
            total_kept = 0
            total_offers = len(self.opponent_offers)
            
            for offer in self.opponent_offers:
                # Items they give me less of, they likely value more
                kept = self.counts[i] - offer[i]
                total_kept += kept
            
            # Normalize to 0-10 scale
            if total_offers > 0:
                avg_kept = total_kept / total_offers
                # Map to value estimate (0-10)
                self.opponent_values_estimate[i] = min(10, int(avg_kept * 10 / self.counts[i]) if self.counts[i] > 0 else 0)
    
    def find_win_win_offer(self, min_value: int) -> Optional[List[int]]:
        """Find an offer that gives me good value while also being good for opponent"""
        best_offer = None
        best_score = -float('inf')
        
        for alloc in self.frontier:
            my_val = self.value_of(alloc)
            if my_val < min_value:
                continue
                
            # Estimate opponent's value
            opp_val = self.opponent_value_estimate(alloc)
            
            # Score combines both values
            score = my_val + opp_val * 0.3  # Weight opponent's value less
            
            if score > best_score:
                best_score = score
                best_offer = alloc
        
        return best_offer
    
    def calculate_time_pressure(self) -> float:
        """Calculate how much pressure we're under due to remaining rounds"""
        rounds_left = self.max_rounds - self.round
        return max(0, 1 - (rounds_left / self.max_rounds) ** 0.7)
    
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.round += 1
        
        # If opponent made an offer
        if o is not None:
            self.opponent_offers.append(o)
            self.update_opponent_model(o)
            
            # Calculate value of opponent's offer
            offer_value = self.value_of(o)
            
            # Calculate time pressure
            time_pressure = self.calculate_time_pressure()
            
            # Dynamic acceptance threshold
            if self.round == 1:
                # First offer: be conservative
                accept_threshold = self.total_value * 0.7
            elif self.round >= self.max_rounds - 1:
                # Last round: be more lenient
                accept_threshold = self.total_value * max(0.4, 0.6 - time_pressure)
            else:
                # Middle rounds: gradual concession
                base_threshold = self.total_value * (self.opening_aggressiveness - 
                                                   time_pressure * (1 - self.min_acceptance_ratio))
                accept_threshold = max(self.total_value * self.min_acceptance_ratio, base_threshold)
            
            # Check if we should accept
            if offer_value >= accept_threshold:
                # Also check if it's a good deal relative to what we can counter with
                can_do_better = False
                if self.round < self.max_rounds:
                    # See if we can get significantly better
                    better_offer = self.find_win_win_offer(offer_value * 1.1)
                    if better_offer is None:
                        return None  # Accept
                    # Accept if the improvement is small
                    better_value = self.value_of(better_offer)
                    if better_value <= offer_value * 1.15:  # Less than 15% better
                        return None  # Accept
                
                return None  # Accept
        
        # Calculate what to demand based on round
        time_pressure = self.calculate_time_pressure()
        
        if self.round == 1:
            # Opening offer: aim high
            target_ratio = self.opening_aggressiveness
        elif self.round >= self.max_rounds:
            # Last possible offer: aim for fair split
            target_ratio = max(self.min_acceptance_ratio, 0.6 - time_pressure * 0.3)
        else:
            # Concession strategy
            base_ratio = self.opening_aggressiveness - time_pressure * (self.opening_aggressiveness - self.min_acceptance_ratio)
            # Add some randomness to avoid being too predictable
            target_ratio = base_ratio * (0.95 + 0.1 * random.random())
        
        target_value = self.total_value * target_ratio
        
        # Find a good offer
        if self.round > 1 and len(self.opponent_offers) > 0:
            # Try to find a win-win based on opponent's preferences
            win_win_offer = self.find_win_win_offer(target_value)
            if win_win_offer is not None:
                return win_win_offer
        
        # Fallback: create a new allocation
        return self.create_allocation_for_ratio(target_ratio)