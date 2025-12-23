# -*- coding: utf-8 -*-
"""
A competitive haggling negotiation agent.

Key ideas
---------
* Sub‑game‑perfect safety target  = ceil(total / (remaining_rounds+1)).
* Opponent model = how many of each item the opponent has *kept*
  in the offers we have seen.
* Counter‑offer:
    1. Take the cheapest collection of items that reaches the safety target.
    2. Hand over items the opponent seems to like most while staying safe.
* Heuristics:
    - Accept a repeated stubborn offer (3 equal offers in a row).
    - Slightly relax the target in the last few rounds to avoid dead‑locks.
"""

from typing import List, Optional


class Agent:
    def __init__(
        self,
        me: int,
        counts: List[int],
        values: List[int],
        max_rounds: int,
    ) -> None:
        # immutable problem data
        self.counts = counts[:]          # total amount of each type
        self.values = values[:]          # our per‑item values
        self.n = len(counts)
        self.total = sum(c * v for c, v in zip(self.counts, self.values))

        # negotiation state
        self.rounds_left = max_rounds            # full rounds still possible
        self.opp_keep = [0] * self.n            # items opponent has kept so far
        self.opp_offers_seen = 0
        self.last_offers: List[List[int]] = []  # history of opponent offers

    # --------------------------------------------------------------------- #
    def _value(self, bundle: List[int]) -> int:
        """Our valuation of a bundle."""
        return sum(b * v for b, v in zip(bundle, self.values))

    # --------------------------------------------------------------------- #
    def _safety_target(self) -> int:
        """
        Classic safety guarantee:
        ceil(total / (remaining_full_rounds + 1)).
        """
        r = self.rounds_left
        if r <= 0:
            return 0
        return (self.total + r) // (r + 1)

    # --------------------------------------------------------------------- #
    def _relaxed_target(self) -> int:
        """
        When we are very close to the deadline we are allowed to concede a
        little.  The relaxed target never goes below the safety target.
        """
        # start relaxing when only 2 rounds left
        if self.rounds_left <= 2:
            # allow us to keep at least 75 % of the safety target
            return max(self._safety_target(), (self._safety_target() * 3) // 4)
        return self._safety_target()

    # --------------------------------------------------------------------- #
    def _update_opp_model(self, offer: List[int]) -> None:
        """Record how many items the opponent kept in the last offer."""
        for i in range(self.n):
            self.opp_keep[i] += self.counts[i] - offer[i]
        self.opp_offers_seen += 1
        self.last_offers.append(offer[:])
        # keep only the last three offers for the “stubborn” rule
        if len(self.last_offers) > 3:
            self.last_offers.pop(0)

    # --------------------------------------------------------------------- #
    def _order_for_us(self) -> List[int]:
        """
        Order used when we pick items for ourselves.
        Prefer high our‑value and low opponent‑keep.
        """
        if self.opp_offers_seen == 0:
            return sorted(range(self.n), key=lambda i: self.values[i], reverse=True)

        return sorted(
            range(self.n),
            key=lambda i: (-self.values[i], self.opp_keep[i]),
        )

    # --------------------------------------------------------------------- #
    def _favored_order_for_opp(self) -> List[int]:
        """
        Order the opponent seems to like (high keep → high assumed value).
        """
        if self.opp_offers_seen == 0:
            return sorted(range(self.n), key=lambda i: self.values[i], reverse=True)

        return sorted(range(self.n), key=lambda i: self.opp_keep[i], reverse=True)

    # --------------------------------------------------------------------- #
    def _make_counter(self) -> List[int]:
        """
        Construct a safe counter‑offer.

        Phase 1 – obtain the safety (or relaxed) target with the cheapest
        items for us.
        Phase 2 – give the opponent as many of his favourite items as possible
        while remaining safe.
        """
        target = self._relaxed_target()
        allocation = [0] * self.n                # items we keep

        # ---------- Phase 1 -------------------------------------------------
        order = self._order_for_us()
        remaining = target

        for i in order:
            if remaining <= 0:
                break
            val = self.values[i]
            if val == 0:
                continue
            available = self.counts[i]
            need = (remaining + val - 1) // val          # ceil division
            take = min(available, need)
            allocation[i] = take
            remaining -= take * val

        # If we could not reach the target (only zero‑value items left)
        # just keep everything – it never harms the guarantee.
        if remaining > 0:
            return self.counts[:]

        # ---------- Phase 2 – generous hand‑outs ---------------------------
        cur_val = self._value(allocation)
        opp_fav = self._favored_order_for_opp()

        for i in opp_fav:
            while allocation[i] > 0 and cur_val - self.values[i] >= target:
                allocation[i] -= 1
                cur_val -= self.values[i]

        return allocation

    # --------------------------------------------------------------------- #
    def _stubborn_offer(self) -> bool:
        """
        Return True if the opponent has repeated the same offer three times.
        Accepting such a “stubborn” offer avoids a zero‑payoff dead‑lock.
        """
        if len(self.last_offers) < 3:
            return False
        return self.last_offers[-1] == self.last_offers[-2] == self.last_offers[-3]

    # --------------------------------------------------------------------- #
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        """
        Called on our turn.

        Parameters
        ----------
        o : list[int] | None
            Opponent's last offer expressed as the bundle we would receive.
            ``None`` on the very first turn when we move first.

        Returns
        -------
        list[int] | None
            * ``None`` – we accept the opponent's offer.
            * list[int] – our counter‑offer (the bundle we would receive).
        """
        # --------------------------------------------------------------
        # we received an offer → a full round has elapsed
        # --------------------------------------------------------------
        if o is not None:
            self.rounds_left -= 1
            self._update_opp_model(o)

            # 1) accept if we already meet the safety target
            if self._value(o) >= self._safety_target():
                return None

            # 2) accept a stubborn, repeated offer even if below target
            if self._stubborn_offer():
                return None

            # otherwise propose a new safe offer
            return self._make_counter()

        # --------------------------------------------------------------
        # no offer → we are the first mover of a new round
        # --------------------------------------------------------------
        return self._make_counter()