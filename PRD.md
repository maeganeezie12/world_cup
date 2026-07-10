# World Cup Guessing Game — PRD

## 1. Overview
A lightweight, self-hosted website for tracking a friends/family/office World Cup guessing game, starting from the Quarterfinal round through the Final. It's a **private, invite-only game**: the whole site sits behind a shared access password (§4), so it isn't publicly reachable — only people you've given the password to can join. Once in, players join, pick match winners round by round, and see a live leaderboard ranked by number of correct picks. **No money changes hands anywhere in this app** — it's purely a prediction/scorekeeping tool; if a group wants to run a side wager on the results, that's entirely their own arrangement, off-platform.

**Remaining matches covered (8 total):** 4 Quarterfinals → 2 Semifinals → 1 Third Place Playoff → 1 Final.

## 2. Goals
- Zero-friction joining — no account creation, no passwords to remember.
- Make it impossible to change a pick after a match kicks off (no cheating with hindsight).
- Give the admin (you) a simple way to enter match results.
- Produce a clear, live-updating leaderboard ranked by correct picks.

## 3. Roles
- **Admin (you):** creates matches, enters real match results, removes players if needed.
- **Player (anyone you've invited):** enters the site access password (§4), joins with a name + short PIN, submits picks for each match, views the leaderboard and their own accuracy.

## 4. Site Access (Private / Invite-Only)
- The entire site sits behind a single shared **access password** — nobody can reach the scoreboard, join page, or picks page until they enter it correctly. This is what keeps the game restricted to people you've actually invited, rather than being an open, publicly-reachable site.
- This is a separate, second layer on top of the other password in this doc: **site access** (anyone invited) and the **admin password** (§8, you only) — plus each player's own **PIN** (§5, personal identity, not a security layer).
- Configurable via the `SITE_PASSWORD` environment variable on the server (defaults to `0000` if unset) — change it if it ever leaks beyond the intended group.

## 5. Joining & Identity
- No email/password login. A player joins by entering a **display name** + a **4-digit PIN** they choose.
- The PIN is only used to re-identify them on later visits (to edit picks before deadline, view their own history) — not for security-grade auth. This is a casual game among people who know each other.
- Duplicate display names get disambiguated (e.g. "Maegan (2)").

## 6. Picks Flow
- Picks are made **match by match**, not as one upfront full-bracket guess:
  1. Once a match's teams are known, the admin opens picks for it.
  2. Each player picks a winner for that match.
  3. Picks lock automatically **1 hour before** that match's kickoff time — only that match locks, every other still-upcoming match stays open independently.
  4. Admin enters the actual result after full-time; each player's win count and accuracy update automatically.
- If a player doesn't submit a pick before kickoff, they simply **sit out that match** — it doesn't count toward their picks made, wins, or accuracy.

## 7. Scoring
- **1 win** per correctly picked match winner. That's it — no bonuses, multipliers, weighting by round, or money of any kind.
- Per player, the app tracks:
  - **Wins** — total correct picks across all settled matches.
  - **Accuracy** — wins ÷ picks made on settled matches, as a %.
  - **Picks made** — how many of the 8 matches they've picked so far (fewer if they joined late and missed early matches).
- The leaderboard ranks by **wins** first, accuracy as a tiebreaker.
- On the Picks page, every match also shows how many people picked each team and who they are — visible any time (open, locked, or settled), not just after results are in.

## 8. Pages / Screens
1. **Enter Password** — the site's front gate. Nothing else is reachable until the correct site access password (§4) is entered; unlocks for the browser session only.
2. **Home / Leaderboard (Scoreboard)** — ranked by wins, then accuracy. Columns per player: Wins, Accuracy, Picks made. Updates automatically as the admin enters each match's result.
3. **Join** — name + PIN, one-time.
4. **My Picks** — enter/edit picks for any currently open match (locks 1 hour before kickoff, per match); shows past picks, per-match vote tallies with voter names, and team flags.
5. **Admin Panel** (protected by a shared admin password, separate from the site access password and player PINs) — create matches, edit team names/kickoff times, enter/clear results, remove a player (and their picks) if needed.

## 9. Data Model (Flask + SQLite)
- `Player`: id, display_name, pin_hash, joined_at
- `Match`: id, type (QF/SF/THIRD_PLACE/FINAL), team_a, team_b, kickoff_at, winner (nullable until result entered)
- `Pick`: id, player_id, match_id, picked_winner, submitted_at
- Wins/accuracy are computed on the fly from `Pick` + `Match.winner` — nothing money-related is stored anywhere.

## 10. Tech Stack
- **Backend:** Python + Flask
- **DB:** SQLite (fine for pool sizes of a few dozen to a few hundred players)
- **Frontend:** Server-rendered templates (Jinja2) + minimal JS for countdowns/live refresh; mobile-friendly since most players will use phones
- **Hosting:** Self-hosted on your own server

## 11. Non-Functional Requirements
- Mobile-responsive — most players will pick via phone.
- Match lock times enforced **server-side** (not just hidden UI) — a player can't submit a pick within 1 hour of kickoff even by hitting the API directly.
- All times displayed in a single agreed timezone (configurable, default to admin's local timezone) to avoid "I thought kickoff was later" disputes.
- No payment or financial data of any kind is handled, stored, or computed by this app.
- Site is **not publicly discoverable/joinable** without the access password (§4) — it's scoped to an invited private group, and framed throughout as a private prediction/scorekeeping tool.

## 12. Out of Scope (for now)
- Any payment processing or money tracking of any kind — deliberately excluded.
- Score-prediction or full-bracket-in-one-go guessing modes.
- Social login / real authentication.
- Public multi-league support (this is a single group instance).
- Bonuses, multipliers, or any weighting beyond flat 1-win-per-correct-pick in §7.

## 13. Match Schedule
All times as shown on the official schedule (source timezone as displayed — confirm/convert to your local timezone before setting kickoff lock times per §11).

**Completed:**

| Match | Round | Result |
|---|---|---|
| France vs Morocco | Quarterfinal | 🇫🇷 France won |

**Upcoming:**

| Match | Round | Kickoff |
|---|---|---|
| Spain vs Belgium | Quarterfinal | Sat, 11 Jul, 3:00 AM |
| Norway vs England | Quarterfinal | Sun, 12 Jul, 5:00 AM |
| Argentina vs Switzerland | Quarterfinal | Sun, 12 Jul, 9:00 AM |
| TBD vs TBD | Semifinal | Wed, 15 Jul, 3:00 AM |
| TBD vs TBD | Semifinal | Thu, 16 Jul, 3:00 AM |
| TBD vs TBD | Third Place Playoff | Not yet listed |
| TBD vs TBD | Final | Not yet listed |

- Semifinal, third place, and final matchups are TBD until the preceding round finishes — picks for each open once the two teams are confirmed.
