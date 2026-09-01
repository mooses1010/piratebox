# Voluntary Check-in Board - Evaluation (Stage 23)

**Status: EVALUATED AND DEFERRED. Nothing in this document is
implemented.** Per instruction, Stage 23 was to "evaluate; defer with
documentation if privacy/complexity concerns can't be resolved simply."
This document is that evaluation. The conclusion is: defer. No code,
data file, or page exists for this feature.

## 1. What was considered

A structured "I'm safe / checked in" board - visitors record their own
name/status (and optionally a short note - "at the shelter", "heading
home") so others on the network can see who has been accounted for, in
the spirit of Red Cross Safe and Well or Google Person Finder, but fully
local and offline.

The immediate appeal is obvious in a real emergency: knowing who is
accounted for is genuinely valuable. But PirateBox's entire trust model -
no accounts, no authentication, anyone on the Wi-Fi can post anything as
anyone - which is exactly right for Chat/Guestbook/Bulletin, becomes a
liability for a feature whose entire point is "an accurate record of who
is safe."

## 2. Why this doesn't clear the bar the other Stage 22-23 features did

**Bulletin Board (Stage 22) already covers the *legitimate* use case.**
Anyone who wants to say "I'm safe, meeting at the school" already can,
right now, as a free-text Bulletin post (Announcement or Info/Update
category). What a *dedicated* check-in board adds beyond that is
exactly the part that's dangerous: a **structured, scannable directory
of named individuals and their claimed status/location** - which is a
fundamentally different, higher-stakes artifact than a scrolling feed of
anonymous-by-default posts.

**Impersonation is not a hypothetical edge case here - it's the central
risk.** With zero authentication:
- Anyone can post "[Real Name] is safe at [location]" for a person who
  is not actually there, is not actually safe, or does not want their
  location disclosed - malicious or well-meaning-but-wrong, either way
  the board would present it with the same authority as a genuine
  self-report.
- Anyone can post that a specific named person is *missing* or *not*
  accounted for - which is its own harm (causing needless alarm, or
  worse, signaling to a bad actor that a specific named person's
  whereabouts are unknown).
- A visible "who has/hasn't checked in" list is itself sensitive: it
  can reveal who is present at a physical location, and just as
  informatively, who is *absent* - to anyone who joins the Wi-Fi network,
  no login required. That is a meaningful information-disclosure/safety
  risk that a plain Bulletin post's less-structured, no-name-required
  format doesn't create in the same way.

**A real Safe and Well-style system solves this with things PirateBox
deliberately does not have and should not add**: account verification,
moderation staff with takedown authority, and typically a relationship
with an actual response organization that can act on the data. None of
that fits a device whose whole design point is "zero infrastructure,
zero accounts, works the same for anyone who joins the Wi-Fi." Building
a half-authenticated version - a name field with no verification behind
it - would be actively worse than not having the feature: it looks
authoritative (a dedicated "Check-in" page, presumably taken more
seriously than a chat message) while offering none of the actual
guarantee that name implies.

**This is a "more fragile" outcome, not just a complexity one.** The
governing instruction for this expansion is explicit: "more capability
must not make PirateBox substantially more fragile." A spoofable safety
directory is fragile in exactly the sense that matters most here - it
can fail (be wrong) silently, at the worst possible moment, in a way
that actively misleads someone relying on it. That is a different, and
worse, kind of fragility than "the CPU temperature stat says unknown."

## 3. Could a narrower version work?

Two narrower variants were considered and also set aside:

- **Self-check-in only, no listing others / no querying by name**: each
  person can only ever see and set their *own* status, never browse a
  directory of names. This removes the "who is/isn't here" disclosure
  risk, but also removes almost all of the feature's value (a check-in
  board nobody but the poster can see isn't meaningfully different from
  that person just remembering they're fine) - and does nothing about
  impersonation, since there's still no way to bind a device/session to
  a specific real name across visits (no accounts, no persistent
  identity by design).
- **Anonymous aggregate counter only** ("N people have checked in as
  safe", no names): removes both disclosure and impersonation risk
  (nothing to impersonate), but is close to worthless operationally - it
  answers "how many," never "is [specific person] safe," which is
  almost always the actual question a worried visitor has.

Neither preserves the feature's real value without reintroducing one of
the two core problems, so neither was pursued as a lesser version.

## 4. Decision

**Defer, do not implement**, as the governing instruction anticipated.
The Bulletin Board (Stage 22) already gives anyone who wants to
self-report status a place to do so, voluntarily, in their own words,
with no false authority attached to it. That is judged sufficient. A
dedicated check-in registry would need real identity/authentication
infrastructure to be *safe*, not just technically simple to build - and
that is out of scope for this project's zero-account, zero-server-trust
design, not merely something skipped for lack of time.

If a future maintainer wants to revisit this, the two open questions to
answer first are exactly the ones above: how to prevent impersonation of
a named individual's status, and how to avoid the board itself becoming
a presence/absence disclosure risk to anyone who joins the network. A
design that doesn't answer both should not ship.
