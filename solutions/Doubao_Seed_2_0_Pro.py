class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts.copy()
        self.values = values.copy()
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.offer_count = 0
        # Sort items by our value descending to prioritize taking highest value first
        self.sorted_items = sorted(range(len(counts)), key=lambda x: (-values[x], counts[x]))
        self.total_possible_offers = 2 * max_rounds
        self.is_last_offerer = 1 if self.total_possible_offers % 2 == 0 else 0  # Always 1 for even total offers

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.offer_count += 1
        offers_done = (self.offer_count * 2) - (1 if self.me == 0 else 0)
        offers_left = self.total_possible_offers - offers_done

        # Edge case: all items are worthless to us, accept any offer or give all away
        if self.total_value == 0:
            return None if o is not None else [0] * len(self.counts)

        # Evaluate incoming offer if present
        if o is not None:
            # Validate offer first, reject if invalid
            valid = True
            offer_val = 0
            for i in range(len(o)):
                if o[i] < 0 or o[i] > self.counts[i]:
                    valid = False
                    break
                offer_val += o[i] * self.values[i]
            if valid:
                # Calculate minimum acceptable value
                if offers_left <= 0:
                    # No more offers if we reject, accept anything >= 0
                    if offer_val >= 0:
                        return None
                else:
                    # Threshold decreases linearly from 80% to 15% as negotiations progress
                    progress = (self.total_possible_offers - offers_left) / max(1, self.total_possible_offers - 1)
                    min_accept = max(0.15 * self.total_value, self.total_value * (0.8 - 0.65 * progress))
                    # If last offer is not ours, lower threshold more in final rounds
                    if self.is_last_offerer != self.me and offers_left <= 2:
                        min_accept = max(0.05 * self.total_value, min_accept * 0.7)
                    if offer_val >= min_accept:
                        return None

        # Build counter offer
        progress = (self.total_possible_offers - offers_left) / max(1, self.total_possible_offers - 1)
        desired_val = min(self.total_value, max(0.2 * self.total_value, self.total_value * (0.9 - 0.6 * progress)))
        my_offer = [0] * len(self.counts)
        current_val = 0

        # Take highest value items first to reach desired value
        for idx in self.sorted_items:
            if current_val >= desired_val or self.values[idx] == 0:
                continue
            max_possible = self.counts[idx]
            take = min(max_possible, (desired_val - current_val) // self.values[idx])
            my_offer[idx] = take
            current_val += take * self.values[idx]

        # If we still need more value, take extra of highest value items
        if current_val < desired_val:
            for idx in self.sorted_items:
                if self.values[idx] == 0:
                    continue
                remaining = self.counts[idx] - my_offer[idx]
                if remaining > 0:
                    take = min(remaining, 1)
                    my_offer[idx] += take
                    current_val += take * self.values[idx]
                    if current_val >= desired_val:
                        break

        # Ensure valid offer (all counts within bounds, zero value items given to partner)
        for i in range(len(my_offer)):
            my_offer[i] = max(0, min(my_offer[i], self.counts[i]))
            if self.values[i] == 0:
                my_offer[i] = 0

        return my_offer