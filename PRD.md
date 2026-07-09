# World Cup Bet League — PRD

## 1. Overview
A lightweight, self-hosted website for tracking a friends/family/office World Cup betting pool, starting from the Quarterfinal round through the Final. Anyone with the link can join, pick match winners round by round, and see a live leaderboard. Money changes hands off-platform (honor system); the site is the single source of truth for who picked what, who's paid, and who's owed what at the end.

**Remaining matches covered (8 total):** 4 Quarterfinals → 2 Semifinals → 1 Third Place Playoff → 1 Final.

## 2. Goals
- Zero-friction joining — no account creation, no passwords to remember.
- Make it impossible to change a pick after a match kicks off (no cheating with hindsight).
- Give the admin (you) a simple way to enter match results and mark who's paid their buy-in.
- Produce a clear, undisputed final payout table at the end of the Final.

## 3. Roles
- **Admin (you):** creates matches, enters real match results, marks buy-ins as paid, publishes final payout.
- **Player (anyone with the link):** joins with a name + short PIN, pays for whichever matches they can still pick (see §5), submits picks for each match, views leaderboard and running winnings.

## 4. Joining & Identity
- No email/password login. A player joins by entering a **display name** + a **4-digit PIN** they choose.
- The PIN is only used to re-identify them on later visits (to edit picks before deadline, view their own history) — not for security-grade auth. This is an honor-system pool among people who know each other.
- Duplicate display names get disambiguated (e.g. "Maegan (2)").

## 5. Buy-In & Payments (Manual / Honor System)
- There's **no fixed $2 charged to everyone**. A player only pays the stakes for the matches they actually have a chance to pick — i.e., matches that haven't kicked off yet at the moment they join.
  - Join before the first Quarterfinal kicks off → full $2 (all 8 matches).
  - Join after the Quarterfinals but before the Semifinals → $1.60 (Semifinal + Third Place + Final only: 2×$0.20 + $0.20 + $1.00).
  - Join after the Semifinals but before the Final/Third Place → $1.20 (Third Place + Final: $0.20 + $1.00).
  - And so on — a player's total buy-in is just the sum of the stakes for whichever matches are still open when they join (see §7 for stake amounts).
- A player is **not** charged for, and cannot pick, matches that have already kicked off before they joined.
- The site does **not** process payment. Players pay the admin directly (cash, PayNow, Venmo, etc.) outside the site.
- Admin has a simple screen listing all joined players, their applicable buy-in total (auto-computed from which matches were still open when they joined), and a "Paid ✅ / Unpaid ❌" toggle.
- No fixed payment deadline — a player can pay **anytime up until the Final's payout is calculated**. Picks count regardless of paid status, but **unpaid players are excluded from the final payout** — flagged clearly on the leaderboard so there's no dispute later.

## 6. Betting Flow
- Picks are made **match by match**, not as one upfront full-bracket guess:
  1. Once a match's teams are known, the admin opens picks for it.
  2. Each player picks a winner for that match.
  3. Picks lock automatically **1 hour before** that match's kickoff time — only that match locks, every other still-upcoming match stays open independently.
  4. Admin enters the actual result after full-time; winnings are calculated automatically.
- If a player doesn't submit a pick before kickoff, they simply **sit out that match** — no stake, no winnings, no loss for that one.

## 7. Scoring & Payout
This is the only payout mechanism — no bonuses, multipliers, or point weighting on top of it.

| Match | Count | Stake per match | Subtotal |
|---|---|---|---|
| Quarterfinal | 4 | $0.10 | $0.40 |
| Semifinal | 2 | $0.20 | $0.40 |
| Third Place Playoff | 1 | $0.20 | $0.20 |
| Final | 1 | $1.00 | $1.00 |
| **Total** | **8** | | **$2.00** |

**How each match settles:**
- Every player who submits a pick for a match puts that match's stake into that match's pot.
- After the result is in, the pot is **split evenly among everyone who picked the winning team**.
- Players who picked wrong get nothing back from that match — their stake stays in the pot and funds the winners' split.
- A player's total winnings = sum of what they receive across all 8 match pots. This is naturally zero-sum (total paid in per match = total paid out per match), so there's no shortfall or rounding gap to reconcile across the group.

## 8. Pages / Screens
1. **Home / Leaderboard (Scoreboard)** — public, ranked by total winnings. Columns per player:
   - **Winnings** — running total $ won across settled match pots (§7).
   - **Accuracy** — correct picks ÷ bets placed (settled matches only), shown as a %.
   - **Bets placed** — count of matches picked so far (out of the 8 total, or fewer if joined late).
   - Paid/unpaid status.
   - Updates automatically as the admin enters each match's result.
2. **Join** — name + PIN, one-time.
3. **My Picks** — enter/edit picks for any currently open match (locks 1 hour before kickoff, per match); shows past picks and winnings per match. Team names shown with country flag icons.
4. **Admin Panel** (protected by a shared admin password, separate from player PINs) — create matches, open/close picking, enter results, toggle paid status, publish final payout.

## 9. Data Model (Flask + SQLite)
- `Player`: id, display_name, pin_hash, paid (bool), joined_at
- `Match`: id, type (QF/SF/THIRD_PLACE/FINAL), stake_amount, team_a, team_b, kickoff_at, winner (nullable until result entered)
- `Pick`: id, player_id, match_id, picked_winner, submitted_at
- `Payout` (computed, not stored): derived per match as pot_total / count_of_correct_pickers, summed per player across all 8 matches

## 10. Tech Stack
- **Backend:** Python + Flask
- **DB:** SQLite (fine for pool sizes of a few dozen to a few hundred players)
- **Frontend:** Server-rendered templates (Jinja2) + minimal JS for countdowns/live refresh; mobile-friendly since most players will use phones
- **Hosting:** Self-hosted on your own server

## 11. Non-Functional Requirements
- Mobile-responsive — most players will pick via phone.
- Match lock times enforced **server-side** (not just hidden UI) — a player can't submit a pick within 1 hour of kickoff even by hitting the API directly.
- All times displayed in a single agreed timezone (configurable, default to admin's local timezone) to avoid "I thought kickoff was later" disputes.
- No real payment data handled — reduces liability/compliance surface significantly.

## 12. Out of Scope (for now)
- Real payment processing (Stripe/PayNow API integration).
- Score-prediction or full-bracket-in-one-go betting modes.
- Social login / real authentication.
- Public multi-league support (this is a single pool instance).
- Bonuses, multipliers, or any payout weighting beyond the flat per-match stakes in §7.

## 13. Match Schedule
All times as shown on the official schedule (source timezone as displayed — confirm/convert to your local timezone before setting kickoff lock times per §11).

| Match | Round | Stake | Kickoff |
|---|---|---|---|
| France vs Morocco | Quarterfinal | $0.10 | Fri, 10 Jul, 4:00 AM |
| Spain vs Belgium | Quarterfinal | $0.10 | Sat, 11 Jul, 3:00 AM |
| Norway vs England | Quarterfinal | $0.10 | Sun, 12 Jul, 5:00 AM |
| Argentina vs Switzerland | Quarterfinal | $0.10 | Sun, 12 Jul, 9:00 AM |
| TBD vs TBD | Semifinal | $0.20 | Wed, 15 Jul, 3:00 AM |
| TBD vs TBD | Semifinal | $0.20 | Thu, 16 Jul, 3:00 AM |
| TBD vs TBD | Third Place Playoff | $0.20 | Not yet listed |
| TBD vs TBD | Final | $1.00 | Not yet listed |

- Semifinal, third place, and final matchups are TBD until the preceding round finishes — picks for each open once the two teams are confirmed.
