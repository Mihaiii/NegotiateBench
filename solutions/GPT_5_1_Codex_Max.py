from typing import List, Optional

class Agent:
    """
    GPT 5.1 Codex Max – revised haggling bot.
    Changes vs previous version:
    - Higher reservation / acceptance floors to avoid lopsided late deals.
    - Smoother concession: target never below ~55% mid-game and ~50% near end.
    - Keep enumeration-based search; score candidates by own value, opp-estimate,
      and closeness to incoming offer.
    - Opponent interest estimation from what they try to keep/give.
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n = len(counts)
        self.max_turns = max_rounds          # number of my turns
        self.turn = 0

        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.best_seen = 0
        self.last_offer_made: Optional[List[int]] = None

        # Opponent interest estimate; neutral prior
        total_items = max(1, sum(counts))
        base = (self.total_value / total_items) if self.total_value > 0 else 1.0
        self.opp_w = [float(base) for _ in range(self.n)]

        # Precompute feasible offers if small state space
        self.candidates: Optional[List[tuple[int, float, List[int]]]] = None
        space = 1
        for c in counts:
            space *= (c + 1)
            if space > 200_000:
                break
        if space <= 200_000:
            tmp: List[tuple[int, float, List[int]]] = []
            self._enum(0, [0] * self.n, tmp)
            tmp.sort(key=lambda x: (-x[0], -x[1]))
            # Deduplicate by my value picking best opp-est
            best_for_val = {}
            for mv, ov, off in tmp:
                if mv not in best_for_val or ov > best_for_val[mv][1]:
                    best_for_val[mv] = (mv, ov, off)
            seen = set()
            cand = []
            for mv, ov, off in list(best_for_val.values()) + tmp[:300]:
                t = tuple(off)
                if t in seen:
                    continue
                seen.add(t)
                cand.append((mv, ov, off))
            self.candidates = cand

    # ---------- helpers ----------
    def _enum(self, idx: int, cur: List[int], acc: List[tuple[int, float, List[int]]]):
        if idx == self.n:
            mv = self._value(cur)
            ov = self._opp_estimate(cur)
            acc.append((mv, ov, cur.copy()))
            return
        for k in range(self.counts[idx] + 1):
            cur[idx] = k
            self._enum(idx + 1, cur, acc)
        cur[idx] = 0

    def _value(self, offer: List[int]) -> int:
        return sum(v * o for v, o in zip(self.values, offer))

    def _opp_estimate(self, offer: List[int]) -> float:
        return sum((self.counts[i] - offer[i]) * self.opp_w[i] for i in range(self.n))

    def _progress(self) -> float:
        if self.max_turns <= 1:
            return 1.0
        return min(1.0, max(0.0, (self.turn - 1) / (self.max_turns - 1)))

    def _accept_threshold(self, last_turn: bool) -> float:
        if self.total_value == 0:
            return 0.0
        prog = self._progress()
        start = 0.95
        end = 0.45 if self.me == 1 else 0.5
        th = self.total_value * (start - (start - end) * prog)
        floor = 0.4 * self.total_value
        if last_turn:
            floor = 0.35 * self.total_value
        return max(th, floor)

    def _target_value(self, last_turn: bool) -> float:
        if self.total_value == 0:
            return 0.0
        hi, lo = 1.0, 0.6
        t = self.total_value * (hi - (hi - lo) * self._progress())
        if last_turn:
            t = max(t, 0.5 * self.total_value)
        return t

    def _concession_order(self) -> List[int]:
        order = []
        for i in range(self.n):
            ratio = (self.values[i] + 0.01) / (self.opp_w[i] + 0.5)
            order.append((ratio, self.values[i], i))
        order.sort(key=lambda x: (x[0], x[1], x[2]))
        return [i for _, _, i in order]

    def _select_offer(
        self,
        target: float,
        forbid: Optional[List[int]],
        incoming: Optional[List[int]]
    ) -> List[int]:
        prog = self._progress()
        w_my = 0.95 - 0.45 * prog      # own weight decreases with time
        w_op = 1.0 - w_my
        dist_weight = 0.1 * prog       # closeness becomes more important later

        if self.candidates:
            chosen = None
            best_score = -1e18
            for mv, ov, off in self.candidates:
                if forbid is not None and off == forbid:
                    continue
                if mv < target and prog < 0.9:
                    continue
                score = w_my * mv + w_op * ov
                if incoming is not None:
                    dist = sum(abs(off[i] - incoming[i]) for i in range(self.n))
                    score -= dist_weight * dist
                if score > best_score:
                    best_score = score
                    chosen = off
            if chosen is None:
                chosen = self.candidates[0][2]
            return chosen.copy()

        # Greedy fallback
        offer = [c for c in self.counts]
        for i, v in enumerate(self.values):
            if v == 0:
                offer[i] = 0
        cur_val = self._value(offer)
        if cur_val <= target:
            if forbid is not None and offer == forbid:
                for i in range(self.n):
                    if offer[i] > 0:
                        offer[i] -= 1
                        break
            return offer

        order = self._concession_order()
        for i in order:
            v = self.values[i]
            while offer[i] > 0 and cur_val - v >= target:
                offer[i] -= 1
                cur_val -= v
            if cur_val <= target:
                break

        if forbid is not None and offer == forbid:
            for i in order:
                if offer[i] > 0:
                    offer[i] -= 1
                    break
        return offer

    def _update_opp_from_offer(self, o: List[int]) -> None:
        for i in range(self.n):
            keep = self.counts[i] - o[i]
            give = o[i]
            if keep > give:
                self.opp_w[i] += 0.5
            elif give > keep:
                self.opp_w[i] = max(0.1, self.opp_w[i] * 0.9)

    # ---------- core ----------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turn += 1
        last_turn = (self.turn == self.max_turns)

        # If nothing is valuable, accept anything
        if self.total_value == 0:
            return None if o is not None else [0] * self.n

        incoming_val = -1
        if o is not None:
            incoming_val = self._value(o)
            self.best_seen = max(self.best_seen, incoming_val)
            self._update_opp_from_offer(o)
            # Accept if they match my last proposal
            if self.last_offer_made is not None and o == self.last_offer_made:
                return None

        # Accept good offers
        if o is not None:
            if incoming_val >= self._accept_threshold(last_turn):
                return None
            # If it is the last turn and better than anything seen, take it
            if last_turn and incoming_val >= self.best_seen and incoming_val > 0:
                return None

        # Construct counter-offer
        target = self._target_value(last_turn)
        forbid = o if o is not None else None
        counter = self._select_offer(target, forbid, o)

        # Avoid deadlock
        if o is not None and counter == o:
            return None

        self.last_offer_made = counter
        return counter