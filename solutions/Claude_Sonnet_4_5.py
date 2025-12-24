class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.me = me
        self.turn = 0
        self.their_offers = []
        self.my_offers = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        total_turns = self.max_rounds * 2
        turns_left = total_turns - self.turn + 1
        
        if o is not None:
            self.their_offers.append(o)
            my_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            if self._should_accept(my_value, turns_left):
                return None
        
        new_offer = self._make_offer(turns_left)
        self.my_offers.append(new_offer)
        return new_offer
    
    def _should_accept(self, offered_value: int, turns_left: int) -> bool:
        """Adaptive acceptance strategy."""
        if self.total_value == 0:
            return True
        
        value_ratio = offered_value / self.total_value
        
        # Always accept on last turn if positive
        if turns_left <= 1:
            return offered_value > 0
        
        # Accept great deals anytime
        if value_ratio >= 0.6:
            return True
        
        # Progressive acceptance thresholds
        if turns_left <= 2:
            return value_ratio >= 0.20
        elif turns_left <= 4:
            return value_ratio >= 0.30
        elif turns_left <= 6:
            return value_ratio >= 0.35
        elif turns_left <= 10:
            return value_ratio >= 0.40
        else:
            return value_ratio >= 0.50
    
    def _make_offer(self, turns_left: int) -> list[int]:
        """Generate offers with strategic concessions."""
        n = len(self.counts)
        
        # Detect deadlock: if we've made same offer 3+ times and they're not budging
        if len(self.my_offers) >= 3 and len(self.their_offers) >= 3:
            if (self.my_offers[-1] == self.my_offers[-2] == self.my_offers[-3] and
                self.their_offers[-1] == self.their_offers[-2] == self.their_offers[-3]):
                # Break deadlock with concession
                if turns_left <= 8:
                    return self._concede_offer(turns_left)
        
        # Calculate target based on time pressure
        target_ratio = self._get_target_ratio(turns_left)
        
        # Estimate opponent values from their behavior
        opp_values = self._estimate_opponent_values()
        
        # Find Nash-optimal offer
        return self._find_nash_offer(target_ratio, opp_values)
    
    def _get_target_ratio(self, turns_left: int) -> float:
        """Calculate target value ratio based on urgency."""
        if turns_left <= 2:
            return 0.25
        elif turns_left <= 4:
            return 0.35
        elif turns_left <= 6:
            return 0.40
        elif turns_left <= 10:
            return 0.45
        elif turns_left <= 16:
            return 0.50
        else:
            return 0.55
    
    def _estimate_opponent_values(self) -> list[float]:
        """Estimate opponent's values from their offers."""
        n = len(self.counts)
        
        if not self.their_offers:
            # No data: assume inverse preference
            max_val = max(self.values) if max(self.values) > 0 else 1
            return [max_val - v + 0.5 for v in self.values]
        
        # Weight recent offers more heavily
        item_demands = [0.0] * n
        total_weight = 0.0
        
        for idx, offer in enumerate(self.their_offers):
            weight = (idx + 1) ** 1.5
            for i in range(n):
                they_keep = self.counts[i] - offer[i]
                item_demands[i] += they_keep * weight
            total_weight += weight
        
        if total_weight == 0:
            return [1.0] * n
        
        # Normalize to get average items they keep
        avg_kept = [d / total_weight for d in item_demands]
        
        # Convert to estimated values (proportional to demand)
        total_demand = sum(avg_kept)
        if total_demand == 0:
            return [1.0] * n
        
        return [max(0.1, (d / total_demand) * self.total_value) for d in avg_kept]
    
    def _find_nash_offer(self, target_ratio: float, opp_values: list[float]) -> list[int]:
        """Find offer maximizing Nash product."""
        n = len(self.counts)
        target_value = target_ratio * self.total_value
        
        # Calculate value efficiency for each item type
        items = []
        for i in range(n):
            if self.counts[i] > 0:
                my_val = self.values[i]
                opp_val = opp_values[i]
                # Ratio indicates comparative advantage
                ratio = my_val / max(opp_val, 0.1)
                items.append((i, ratio, my_val, opp_val))
        
        # Sort by comparative advantage
        items.sort(key=lambda x: -x[1])
        
        # Greedy allocation based on comparative advantage
        offer = [0] * n
        current_value = 0
        
        for item_type, ratio, my_val, opp_val in items:
            # Take items where we have comparative advantage
            if ratio >= 1.0 or current_value < target_value:
                take = self.counts[item_type]
                offer[item_type] = take
                current_value += take * my_val
        
        # If we're asking for too much, give back low-value items
        if current_value > target_value * 1.2:
            for item_type, ratio, my_val, opp_val in reversed(items):
                while offer[item_type] > 0 and current_value > target_value * 1.1:
                    offer[item_type] -= 1
                    current_value -= my_val
        
        # Ensure we ask for at least target
        if current_value < target_value:
            for item_type, ratio, my_val, opp_val in items:
                while offer[item_type] < self.counts[item_type] and current_value < target_value:
                    offer[item_type] += 1
                    current_value += my_val
        
        return offer
    
    def _concede_offer(self, turns_left: int) -> list[int]:
        """Make a concession to break deadlock."""
        if not self.their_offers:
            return self._find_nash_offer(0.4, self._estimate_opponent_values())
        
        # Take their last offer and improve it slightly for us
        their_last = self.their_offers[-1]
        offer = their_last[:]
        
        # Try to claim one more valuable item
        best_swap = None
        best_gain = 0
        
        for i in range(len(offer)):
            if offer[i] < self.counts[i] and self.values[i] > best_gain:
                best_gain = self.values[i]
                best_swap = i
        
        if best_swap is not None:
            offer[best_swap] += 1
        
        return offer