# Gap 1: money, licence and platform gate before the Meshy trial

All pages read on 2026-10-02. Budget: 25 tool calls, all used; Sloyd was not checked (dropped for breadth).
`[unconfirmed]` = no primary source opened (forum, third-party blog, memory or inference).

## 1. Paying from Ukraine

| Service | Processor and methods (source) | Ukraine | Discount, VAT |
|---|---|---|---|
| Meshy | Stripe; "all major credit cards", Cash App Pay, Apple Pay, Link, iDEAL; wire transfer for Enterprise only. **No PayPal listed.** (https://www.meshy.ai/pricing FAQ; terms §4 says billing runs through third-party payment providers, https://www.meshy.ai/terms-of-use) | Terms have no country, sanctions or Ukraine clause (terms of 2026-09-19). Whether a Ukrainian Visa/Mastercard passes Stripe checkout is `[unconfirmed]`: Stripe does not onboard Ukrainian *merchants*, but buyers' cards are normally accepted (memory). | Pricing page: "50% off first month on monthly plans", "20% off annual", for new users; no region condition stated. VAT: not stated on the page; whether Stripe Tax adds Ukrainian 20% VAT on e-services is `[unconfirmed]`. |
| Tripo | Stripe, Inc. (Tripo terms, https://developers.tripo3d.ai/en/terms, last updated 2025-07-11) | No restricted-country list; "responsible for compliance with local law". Pricing page returned 403, so methods and price `[unconfirmed]`. | `[unconfirmed]` |
| itch.io (Quaternius) | PayPal (balance, card, bank) or Stripe (card), chosen by the *seller's* payout setup (https://itch.io/docs/creators/payments, from search snippet) | Forum threads say Ukrainian *sellers* hit PayPal/Stripe walls (https://itch.io/t/3122625/...). A Ukrainian *buyer* paying a non-Ukrainian seller (Quaternius) with a card via Stripe or with a Ukrainian PayPal account (PayPal opened sending in Ukraine in 2022, memory) should work: `[unconfirmed]`. | Pay-what-you-want with minimums (below). |
| Sloyd | not checked | not checked | not checked |

Practical test (zero cost risk): on the trial evening the human opens checkout and sees whether the card is accepted and whether VAT is added before confirming. Recommend a card with online foreign payments enabled (Monobank/PrivatBank cards usually are, `[unconfirmed]`).

## 2. Meshy terms vs a PUBLIC repo

- Ownership: terms §3.2 (2026-09-19): paid plan, the customer owns the Customer Output; Meshy keeps a non-exclusive royalty-free licence to use it to run the service. Free plan: Meshy owns it and licenses it CC BY 4.0. **Confirmed.** https://www.meshy.ai/terms-of-use
- Redistribution: §2.6 forbids reselling or redistributing *the Service* or access to it and using outputs to train competing models; nothing forbids publishing owned outputs. So owned GLBs (auto-rigged, animated) may legally sit in a public repo. That the library motions inside an export count as "output" is an inference: the animation library page says "Animated exports follow your plan's license" and Pro+ "include commercial-use rights for games" (https://www.meshy.ai/animation-library). No explicit statement covers raw motion files alone. `[inference]`
- Contradiction: the animation library page says "free-tier output is for personal and evaluation use", while terms §3.2 say free output is CC BY 4.0 (commercial with attribution). The terms win legally, but it is a reason not to ship free-tier output.
- Motion provenance: the library page (631 animations: Walk & Run 150, Daily 155, Fighting 146, Body 147, Dancing 33; 22 free on every plan) says nothing about the source (mocap, Mixamo, licensed). **Unknown.** #165's "591" is now 631.
- Training: terms §2.9 let Meshy train on inputs and outputs of all non-Enterprise customers; the pricing FAQ says "no training use without consent". Contradiction; the terms govern.
- After cancelling: help article (updated 2026-08-27): "You'll retain the rights to the models you created while you were a subscriber, and they will remain private indefinitely." Models do not revert to CC BY. **Confirmed.** https://help.meshy.ai/en/articles/9992023
- Public-repo caveat: "owned" does not stop people copying files from a public repo; the repo licence must not accidentally grant them (the game repo's code licence must exclude art, or the credits entry states "all rights reserved, Meshy paid output owned by xperiaroco2"). `[inference]`

## 3. Mixamo

The Adobe FAQ (https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html) returned 403; web.archive.org cannot be fetched by this tool. From memory: free with an Adobe ID, royalty-free in commercial games, but characters and animations may not be redistributed or sold as stand-alone files (only inside a game/project). `[unconfirmed]`. Consequence: raw Mixamo FBX must stay out of the public game repo; baked into a shipped character inside a game build is allowed. Human check: open that URL in a browser and read the "Can I distribute..." answer.

## 4. Tripo

- Terms (https://developers.tripo3d.ai/en/terms, 2025-07-11; https://www.tripo3d.ai/terms gave 403): paid users own inputs and outputs, may use them commercially; Tripo **will not** train on paid users' inputs/outputs. Free users: Tripo retains all rights (no commercial use). Hong Kong law, HKIAC arbitration. After termination: access lost; public content may be kept forever, private content may be deleted (download everything before cancelling).
- API V2: no maintenance from 2026-10-01 00:00 UTC+8; **retired 2026-11-01 00:00 UTC+8**, all V2 endpoints stop. Primary: https://docs.tripo3d.ai/get-started/introduction.html. V3 base `https://openapi.tripo3d.ai/v3` (from tryAGI SDK, https://github.com/tryAGI/Tripo, `[unconfirmed]`). Any tooling we write must target V3 only.
- Price $19.9/month: pricing page 403, `[unconfirmed]`.

## 5. GitHub Free private repos

https://docs.github.com/en/get-started/learning-about-github/githubs-plans lists "Protected branches", "Required pull request reviewers", "Code owners" for private repos under **GitHub Pro**, not GitHub Free for personal accounts. **Confirmed.** Rulesets: same split (public on Free, private needs Pro/Team) from memory `[unconfirmed]` (the rulesets page excerpt mentioned only Team/Enterprise for org-wide rulesets, https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets).
Options for prime-game-art's main guard: (a) local pre-push hook like the game repo (blocks accidents, no cost; recommended for a hobby project); (b) GitHub Pro for the owner (paid, human decision; price not checked); (c) make the art repo public (rejected: drafts and paid outputs).

## 6. Steam AI disclosure

https://partner.steamgames.com/doc/gettingstarted/contentsurvey (no date on the page): Pre-Generated = content "created with the help of AI tools during development" that ships and is consumed by players (art, sound, narrative, localization) — must be described; Live-Generated = created while the game runs — must also describe guardrails against illegal content. Efficiency tools built into dev environments are "not the focus". **Confirmed.** Human-reworked AI assets are not explicitly addressed; "with the help of AI tools" covers them, so disclose. `[inference]` The January 2026 rewrite that exempts code assistants is reported by third parties (e.g. https://respawn.outlookindia.com/gaming/gaming-news/valve-clarifies-steam-ai-policy-focus-shifts-to-content-consumed) `[unconfirmed date]`. For prime-game: Meshy/Tripo characters = Pre-Generated disclosure; Claude-written code = not disclosed.

## Licences

| Name | Licence | Commercial | Attribution | Public repo |
|---|---|---|---|---|
| Meshy paid output | owned by customer (terms §3.2) | yes | no | yes by terms (inference), keep "all rights reserved" note |
| Meshy free output | CC BY 4.0 | yes per terms (page says personal/eval) | yes | yes, but avoid |
| Tripo paid output | owned by customer | yes | no | yes (terms silent on limits) |
| Tripo free output | Tripo owns | no | - | no |
| Quaternius UAL (Standard free 45 anims; Pro $9.99+ 120+ anims FBX/GLB incl. Godot export; Source $14.99+ adds .blend) | CC0 | yes | no | yes |
| Mixamo | Adobe terms, royalty-free | yes | no | no for raw files `[unconfirmed]` |
