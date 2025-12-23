import math
import random
from typing import List, Optional


class Agent:
    """
    Negotiation agent for the Haggling challenge.

    Key features:
    - Learns opponent preferences from what they keep/give in their offers.
    - Maintains a soft interval estimate of opponent acceptance threshold (as fraction of total).
    - Chooses counter-offers by maximizing expected utility (my_value * P(accept)),
      using either exact enumeration (when the space is small) or a heuristic candidate search.
    """

    # ------------------------------- Init -------------------------------

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = int(me)
        self.counts = list(map(int, counts))
        self.values = list(map(int, values))
        self.max_rounds = int(max_rounds)

        self.n = len(self.counts)
        self.total = sum(c * v for c, v in zip(self.counts, self.values))
        self.turn = 0  # 0..max_rounds-1 (our turns only)

        self.best_received = 0

        # Opponent preference signals: what they keep vs what they give us (from their offers).
        self.kept_sum = [0.0] * self.n
        self.given_sum = [0.0] * self.n

        # Opponent acceptance threshold bounds as fractions of total value (0..1).
        # lb: they likely need at least this; ub: they likely accept at most this (soft).
        self.opp_lb_f = 0.0
        self.opp_ub_f = 1.0

        # Track our last offer's estimated opponent fraction (for "they rejected it" update).
        self._last_sent_offer: Optional[List[int]] = None
        self._last_sent_opp_frac: Optional[float] = None

        # Precompute for enumeration pruning.
        self._suffix_my_max = [0] * (self.n + 1)
        for i in range(self.n - 1, -1, -1):
            self._suffix_my_max[i] = self._suffix_my_max[i + 1] + self.counts[i] * self.values[i]

        # Deterministic-ish RNG (no persistence across sessions).
        seed = (sum(self.counts) + 31 * sum(self.values) + 131 * self.max_rounds + 7 * self.me) & 0xFFFFFFFF
        self._rng = random.Random(seed)

    # ------------------------------ Utils ------------------------------

    def _my_value(self, offer_to_me: List[int]) -> int:
        return sum(v * x for v, x in zip(self.values, offer_to_me))

    def _progress(self) -> float:
        if self.max_rounds <= 1:
            return 1.0
        return min(1.0, max(0.0, self.turn / (self.max_rounds - 1)))

    @staticmethod
    def _sigmoid(x: float) -> float:
        # Safe logistic
        if x <= -30.0:
            return 0.0
        if x >= 30.0:
            return 1.0
        return 1.0 / (1.0 + math.exp(-x))

    def _valid_offer(self, o: List[int]) -> bool:
        return (
            isinstance(o, list)
            and len(o) == self.n
            and all(isinstance(x, int) for x in o)
            and all(0 <= o[i] <= self.counts[i] for i in range(self.n))
        )

    # --------------- Opponent modeling (from their offers) --------------

    def _update_from_their_offer(self, o: List[int]) -> None:
        for i in range(self.n):
            given = o[i]
            kept = self.counts[i] - o[i]
            if given > 0:
                self.given_sum[i] += given
            if kept > 0:
                self.kept_sum[i] += kept

    def _opp_unit_values_scaled(self) -> List[float]:
        """
        Build opponent pseudo unit-values from (kept/given) ratios, then scale so that
        sum(counts[i]*opp_unit[i]) == our total (given in problem statement).
        """
        if self.total <= 0:
            return [0.0] * self.n

        # Preference weight: high if they keep it a lot and give it rarely.
        weights = []
        for i in range(self.n):
            w = (self.kept_sum[i] + 1.0) / (self.given_sum[i] + 1.0)
            # Slightly downweight types with zero availability noise (still fine).
            weights.append(max(1e-6, w))

        denom = sum(self.counts[i] * weights[i] for i in range(self.n))
        if denom <= 0:
            return [0.0] * self.n
        scale = self.total / denom
        return [w * scale for w in weights]

    def _opp_value_of_their_share(self, offer_to_me: List[int], opp_unit: List[float]) -> float:
        # Opponent gets (counts - offer_to_me)
        return sum((self.counts[i] - offer_to_me[i]) * opp_unit[i] for i in range(self.n))

    def _opp_frac_of_total(self, offer_to_me: List[int], opp_unit: List[float]) -> float:
        if self.total <= 0:
            return 0.0
        return self._opp_value_of_their_share(offer_to_me, opp_unit) / float(self.total)

    def _update_opp_threshold_bounds(self, their_offer: Optional[List[int]], opp_unit: List[float]) -> None:
        """
        Update opponent threshold bounds:
        - If they rejected our last offer (i.e., we now see a new offer from them),
          then their required value is likely > opp_frac(last_offer).
        - If they make an offer, their own demanded share is an upper bound-ish
          (threshold is <= what they demand), with slack.
        """
        # Rejection update (soft lower bound)
        if their_offer is not None and self._last_sent_opp_frac is not None:
            # Add a small margin because rejection implies "not enough for them"
            self.opp_lb_f = max(self.opp_lb_f, min(1.0, self._last_sent_opp_frac + 0.02))

        # Their offer update (soft upper bound with slack; they can demand > minimum)
        if their_offer is not None:
            frac = self._opp_frac_of_total(their_offer, opp_unit)
            self.opp_ub_f = min(self.opp_ub_f, min(1.0, frac + 0.10))

        # Keep interval sane
        if self.opp_lb_f > self.opp_ub_f:
            mid = 0.5 * (self.opp_lb_f + self.opp_ub_f)
            self.opp_lb_f = max(0.0, mid - 0.05)
            self.opp_ub_f = min(1.0, mid + 0.05)

    # ------------------------ Our accept policy ------------------------

    def _accept_threshold_value(self) -> float:
        """
        Our minimum acceptable value (in our utility units) at current turn.
        """
        if self.total <= 0:
            return 0.0

        p = self._progress()
        # Firm early, concede over time: ~0.88 -> ~0.38
        frac = 0.88 - 0.50 * p

        # Last move adjustments: if we are second, rejecting ends negotiations.
        if self.turn >= self.max_rounds - 1:
            if self.me == 1:
                frac = min(frac, 0.25)
            else:
                frac = min(frac, 0.32)

        # Don't drop far below best seen unless very late.
        guard = self.best_received - (0.03 + 0.05 * p) * self.total
        floor = max(frac * self.total, guard)

        # Never accept a truly tiny fraction unless total is zero anyway.
        floor = max(floor, 0.12 * self.total)
        return min(self.total, max(0.0, floor))

    # ------------------------ Offer optimization ------------------------

    def _opp_accept_params(self) -> tuple[float, float]:
        """
        Returns (theta_f, k_f) for acceptance probability model:
            P(accept) = sigmoid((opp_frac - theta_f) / k_f)
        """
        p = self._progress()
        # Prior schedule for opponent threshold fraction (decreasing over time).
        base = 0.60 - 0.30 * p  # 0.60 -> 0.30
        theta_f = min(max(base, self.opp_lb_f), self.opp_ub_f)

        spread = max(0.0, self.opp_ub_f - self.opp_lb_f)
        k_f = max(0.05, 0.5 * spread + 0.06)  # softness
        return theta_f, k_f

    def _score_offer(self, offer: List[int], opp_unit: List[float], floor_value: float) -> float:
        myv = self._my_value(offer)
        if myv + 1e-9 < floor_value:
            return -1e30  # hard floor

        opp_frac = self._opp_frac_of_total(offer, opp_unit)
        theta_f, k_f = self._opp_accept_params()
        prob = self._sigmoid((opp_frac - theta_f) / k_f)

        # Primary objective: maximize expected utility; small tie-break toward their acceptance.
        return myv * prob + 0.02 * (opp_frac * self.total)

    def _search_by_enumeration(self, opp_unit: List[float], floor_value: float) -> List[int]:
        best_offer = [0] * self.n
        best_score = -1e30

        offer = [0] * self.n

        def rec(i: int, myv: int) -> None:
            nonlocal best_score, best_offer

            # Prune: even taking all remaining can't reach floor.
            if myv + self._suffix_my_max[i] < floor_value:
                return

            if i == self.n:
                sc = self._score_offer(offer, opp_unit, floor_value)
                if sc > best_score:
                    best_score = sc
                    best_offer = offer[:]
                return

            # Iterate high to low: tends to keep my value high and helps pruning
            c = self.counts[i]
            v = self.values[i]
            for q in range(c, -1, -1):
                offer[i] = q
                rec(i + 1, myv + q * v)

        rec(0, 0)
        return best_offer

    def _greedy_offer_for_target(self, target_my_value: float, opp_unit: List[float]) -> List[int]:
        """
        Take everything, then concede units that give opponent high value per our cost,
        while keeping my_value >= target.
        """
        offer = self.counts[:]

        # Give away all zero-value items immediately.
        for i in range(self.n):
            if self.values[i] == 0:
                offer[i] = 0

        myv = self._my_value(offer)
        if myv <= target_my_value or self.total <= 0:
            return offer

        ratios = []
        for i in range(self.n):
            if offer[i] > 0 and self.values[i] > 0:
                ratios.append((opp_unit[i] / self.values[i], i))
        ratios.sort(reverse=True)

        for _, i in ratios:
            if myv <= target_my_value:
                break
            v = self.values[i]
            if v <= 0:
                continue
            slack = myv - target_my_value
            give = min(offer[i], int(slack // v))
            if give > 0:
                offer[i] -= give
                myv -= give * v

        return offer

    def _search_heuristic(self, opp_unit: List[float], floor_value: float) -> List[int]:
        p = self._progress()
        candidates: List[List[int]] = []

        # A few greedy targets (start high, drift down toward floor)
        start = min(self.total, (0.93 - 0.40 * p) * self.total)
        start = max(start, floor_value + 0.02 * self.total)
        step = 0.06 * self.total
        for k in range(7):
            tgt = max(floor_value, start - k * step)
            candidates.append(self._greedy_offer_for_target(tgt, opp_unit))
        candidates.append(self._greedy_offer_for_target(floor_value, opp_unit))

        # Randomized concessions guided by opp/our ratio.
        # (More concessions for types opponent seems to care about and we care less about.)
        for _ in range(140):
            off = self.counts[:]
            for i in range(self.n):
                if self.values[i] == 0:
                    off[i] = 0
                    continue
                if self.counts[i] == 0:
                    continue
                ratio = opp_unit[i] / (self.values[i] + 1e-9)
                # Concession intensity increases over time.
                inten = (0.25 + 0.65 * p) * (ratio / (1.0 + ratio))
                give = int(round(inten * self.counts[i] + self._rng.random() * 0.75))
                off[i] = max(0, self.counts[i] - min(self.counts[i], give))
            candidates.append(off)

        # Evaluate and pick best, then do small local improvements.
        best = candidates[0]
        best_score = -1e30
        for off in candidates:
            sc = self._score_offer(off, opp_unit, floor_value)
            if sc > best_score:
                best_score = sc
                best = off

        # Local search: single-unit tweaks.
        best2 = best[:]
        best2_score = best_score
        for _ in range(90):
            improved = False
            for i in range(self.n):
                if self.counts[i] <= 0:
                    continue

                # Try giving one more unit (if possible).
                if best2[i] > 0:
                    t = best2[:]
                    t[i] -= 1
                    sc = self._score_offer(t, opp_unit, floor_value)
                    if sc > best2_score:
                        best2, best2_score = t, sc
                        improved = True

                # Try taking one more unit (if possible).
                if best2[i] < self.counts[i]:
                    t = best2[:]
                    t[i] += 1
                    sc = self._score_offer(t, opp_unit, floor_value)
                    if sc > best2_score:
                        best2, best2_score = t, sc
                        improved = True
            if not improved:
                break

        return best2

    def _choose_counter_offer(self) -> List[int]:
        if self.total <= 0:
            return [0] * self.n

        opp_unit = self._opp_unit_values_scaled()
        floor_value = self._accept_threshold_value()

        # If the offer space is small, enumerate exactly.
        space = 1
        for c in self.counts:
            space *= (c + 1)
            if space > 60000:
                break

        if space <= 60000:
            offer = self._search_by_enumeration(opp_unit, floor_value)
        else:
            offer = self._search_heuristic(opp_unit, floor_value)

        # Store info for rejection-based update next time.
        self._last_sent_offer = offer[:]
        self._last_sent_opp_frac = self._opp_frac_of_total(offer, opp_unit)
        return offer

    # ------------------------------ API --------------------------------

    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        idx = self.turn
        self.turn += 1

        if self.total <= 0:
            # If nothing matters to us, accept any valid offer, else propose zeros.
            if o is not None and self._valid_offer(o):
                return None
            return [0] * self.n

        # Process opponent offer if present.
        if o is not None:
            if not self._valid_offer(o):
                # Environment glitch or invalid input; respond with a safe valid counter.
                return self._choose_counter_offer()

            self.best_received = max(self.best_received, self._my_value(o))

            # Update opponent preference model and threshold bounds.
            self._update_from_their_offer(o)
            opp_unit = self._opp_unit_values_scaled()
            self._update_opp_threshold_bounds(o, opp_unit)

            v = self._my_value(o)
            if v >= self._accept_threshold_value():
                return None

            # If we are second and this is our last decision, avoid ending with 0 too often.
            if self.me == 1 and idx >= self.max_rounds - 1:
                if v >= 0.15 * self.total:
                    return None

        else:
            # No incoming offer (we start). Reset last-sent info.
            self._last_sent_offer = None
            self._last_sent_opp_frac = None

        return self._choose_counter_offer()