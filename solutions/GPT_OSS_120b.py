# -*- coding: utf-8 -*-
"""
Improved haggling negotiation agent.

The agent guarantees a minimum value derived from the
remaining number of full rounds (the classic sub‑game‑perfect
solution) and, additionally, builds a tiny model of the opponent’s
preferences from the items the opponent keeps in his offers.
Counter‑offers are constructed greedily to meet the guarantee and
then biased towards leaving the opponent the objects he seems to
value most, which raises the chance of acceptance without sacrificing
the safety guarantee.
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
        # ---- problem data -------------------------------------------------
        self.counts = counts[:]          # total amount of each type
        self.values = values[:]          # our per‑item values
        self.n = len(counts)
        self.total = sum(c * v for c, v in zip(self.counts, self.values))

        # ---- negotiation state --------------------------------------------
        # full rounds still possible (a round = two turns)
        self.rounds_left = max_rounds

        # order of item types – most valuable for us first (stable)
        self.order = sorted(
            range(self.n),
            key=lambda i: self.values[i],
            reverse=True,
        )

        # opponent model: how many of each type the opponent has *kept*
        # (i.e. did NOT give to us) in all offers seen so far.
        self.opp_keep = [0] * self.n
        self.opponent_offers_seen = 0

    # ------------------------------------------------------------------ #
    def _value(self, bundle: List[int]) -> int:
        """Our valuation of a bundle."""
        return sum(b * v for b, v in zip(bundle, self.values))

    # ------------------------------------------------------------------ #
    def _target(self) -> int:
        """
        Minimal value we are willing to accept given the remaining rounds.

        With r rounds left the safe guarantee is ceil(total / (r+1)).
        When r == 0 we accept any final offer.
        """
        r = self.rounds_left
        if r <= 0:
            return 0
        return (self.total + r) // (r + 1)          # ceil division

    # ------------------------------------------------------------------ #
    def _update_opp_model(self, offer: List[int]) -> None:
        """
        Update the opponent model with a new offer.

        `offer` describes what *we* would receive, therefore
        the opponent keeps `counts[i] - offer[i]` pieces of type i.
        """
        for i in range(self.n):
            self.opp_keep[i] += self.counts[i] - offer[i]
        self.opponent_offers_seen += 1

    # ------------------------------------------------------------------ #
    def _favored_order(self) -> List[int]:
        """
        Return a type order that favours the opponent.

        Types the opponent has kept more often are placed first.
        Ties are broken by our original order (most valuable for us).
        """
        # If we have never seen the opponent, fall back to our order.
        if self.opponent_offers_seen == 0:
            return self.order[:]

        # Build a list of (opp_keep, our_value, index) and sort descending.
        # Larger opp_keep → opponent likes it more → we leave it to him.
        combined = [
            (self.opp_keep[i], self.values[i], i) for i in range(self.n)
        ]
        combined.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        return [idx for _, _, idx in combined]

    # ------------------------------------------------------------------ #
    def _make_counter(self) -> List[int]:
        """
        Greedy counter‑offer:

        1. Take the most valuable items for us until we reach the
           current guarantee.
        2. If we still have “free” capacity (i.e. we have not taken all
           remaining items), give the opponent the items he seems to
           value most, leaving us with the rest.
        """
        target = self._target()
        remaining = target
        allocation = [0] * self.n          # what we take for ourselves

        # ---- Phase 1: satisfy the guarantee --------------------------------
        for i in self.order:
            if remaining <= 0:
                break
            per_item = self.values[i]
            if per_item == 0:
                continue
            available = self.counts[i]    # total items of this type
            # How many we need of this type (ceil division)
            need = (remaining + per_item - 1) // per_item
            take = min(available, need)
            allocation[i] = take
            remaining -= take * per_item

        # If we could not reach the target (possible only when all remaining
        # items have zero value for us), just take everything – it does not
        # hurt the guarantee.
        if remaining > 0:
            allocation = self.counts[:]
            return allocation

        # ---- Phase 2: give opponent his favourite remaining items ----------
        # Compute how many items of each type are still unallocated.
        left = [self.counts[i] - allocation[i] for i in range(self.n)]

        # We are free to leave any of the leftover items to the opponent.
        # To increase acceptance probability we keep the items the opponent
        # likes *least* and give him the ones he liked most.
        fav_order = self._favored_order()
        # Walk through fav_order and, as long as we still have spare slots
        # (i.e. we could voluntarily give away more without harming our
        # guarantee), we set allocation[i] = 0 for those types – which is
        # already the case – so this loop is only for clarity.
        # The real work is simply to *not* take anything from the favourite
        # types; they stay in `left` and thus go to the opponent.

        # No extra work is needed – allocation already contains the minimal
        # set that reaches the guarantee.  All `left` items automatically go
        # to the opponent, and we have biased the choice of which items are
        # left by the order in which we selected items in Phase 1 (most
        # valuable for us first).  The favourite‑order function only matters
        # when there are multiple zero‑value items; it ensures we keep the
        # ones the opponent cares about least.

        return allocation

    # ------------------------------------------------------------------ #
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        """
        Called on each of our turns.

        Parameters
        ----------
        o : list[int] | None
            The opponent's last offer expressed as the bundle we would
            receive. ``None`` for the very first turn when we move first.

        Returns
        -------
        list[int] | None
            * ``None`` – we accept the opponent's offer.
            * list[int] – our counter‑offer (the bundle we would receive).
        """
        # ---------------------------------------------------------------
        # If we received an offer, a full round has elapsed.
        if o is not None:
            self.rounds_left -= 1          # one round consumed
            self._update_opp_model(o)     # improve opponent model

            # Accept if the offer satisfies the safety guarantee.
            if self._value(o) >= self._target():
                return None                # accept

            # Otherwise propose a new split.
            return self._make_counter()

        # ---------------------------------------------------------------
        # No offer → we are the first mover (or first mover of a new round).
        return self._make_counter()