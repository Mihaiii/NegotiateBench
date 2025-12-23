class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts[:]
        self.values = values[:]
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_rounds = max_rounds
        self.call_count = 0
        self.opp_claims = []
        self.last_my_claim = None

    def val(self, share):
        return sum(s * v for s, v in zip(share, self.values))

    def offer(self, o: list[int] | None) -> list[int] | None:
        remaining_my_turns = self.max_rounds - self.call_count
        frac_rem = remaining_my_turns / self.max_rounds if self.max_rounds > 0 else 0.0
        self.call_count += 1

        if o is not None:
            opp_claim = [self.counts[i] - o[i] for i in range(len(self.counts))]
            self.opp_claims.append(opp_claim[:])
            o_val = self.val(o)
            accept_thresh = self.total * (0.2 + 0.8 * frac_rem)
            is_last_turn = (self.me == 1) and (self.call_count == self.max_rounds)
            if (o_val >= accept_thresh or
                (remaining_my_turns <= 1 and o_val >= 0.2 * self.total) or
                (is_last_turn and o_val > 0)):
                return None

        # Counter offer
        if self.last_my_claim is None:
            my_claim = self.counts[:]
            for i in range(len(my_claim)):
                if self.values[i] == 0:
                    my_claim[i] = 0
        else:
            my_claim = self.last_my_claim[:]

        curr_val = self.val(my_claim)
        target = self.total * (0.5 + 0.5 * frac_rem)

        # Compute avg_opp_frac
        avg_opp_frac = [0.0] * len(self.counts)
        if self.opp_claims:
            n_hist = len(self.opp_claims)
            for i in range(len(self.counts)):
                if self.counts[i] > 0:
                    avg_opp_frac[i] = sum(claim[i] for claim in self.opp_claims) / (n_hist * self.counts[i])

        while curr_val > target * 1.05 and any(my_claim[i] > 0 for i in range(len(my_claim))):
            candidates = []
            for i in range(len(my_claim)):
                if my_claim[i] > 0:
                    score = avg_opp_frac[i] * 20 - self.values[i] * 0.5
                    candidates.append((score, i))
            if not candidates:
                break
            candidates.sort(reverse=True)
            i = candidates[0][1]
            my_claim[i] -= 1
            curr_val -= self.values[i]

        self.last_my_claim = my_claim[:]
        return my_claim