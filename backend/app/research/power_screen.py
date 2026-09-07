"""Programme-level power screen, and why the FX search terminated.

WHAT THIS MODULE IS
After 24 candidates, the binding constraint turned out not to be idea quality.
It was arithmetic. This records the screen that established that, so nobody
repeats the search without first checking whether the data can answer.

THE SCREEN

For any event-conditioned FX study, an effect must clear TWO thresholds at
once. It must cover the round-trip toll, and what remains must be large enough
to detect at the sample size the event frequency allows:

    need_gross = 1.65 * sigma / sqrt(n)  +  toll

Both are paid. Taking the maximum of them, as an earlier version of this screen
did, understates the requirement and was corrected.

RESULTS - CANDIDATES 25 TO 30, SCREENED BEFORE EXECUTION

    candidate                        n   sigma   toll   detect   viable
    C25  quarter-end WMR            64    16.7   0.93     3.44      no
    C25b non-quarter month-end     128    16.7   0.93     2.44      no
    C26  triple-swap Wednesday     829     7.7   1.15     0.44     yes
    C27  daily post-fix vs SPY    4975    12.5   0.93     0.29     yes
    C28  Tokyo fix daily          4975     8.4   0.72     0.20     yes
    C29  ECB 14:15 month-end       192    17.8   0.85     2.12      no
    C30  day-of-week at the fix    995    16.7   0.93     0.87     yes

The screen retro-validates on the one case already measured: month-end WMR
needed 3.12 bp of detection floor and delivered 2.31 bp net, which is why its
t was 1.23. It was never detectable, and the screen says so without running it.

Three candidates were therefore never run. C29 in particular - the ECB 14:15
CET month-end fix - was the proposed next study and is provably underpowered
at 192 events before a line of it is executed.

RESULTS - THE FOUR THAT WERE VIABLE, ALL REFUTED

    C26  triple-swap Wednesday. Every weekday shows positive drift at the
         22:00 London rollover hour (t +2.57 to +4.41). That is a uniform
         rollover artefact, not a Wednesday effect, and every best-side net is
         negative (-0.185 to -0.500 bp).

    C27  daily post-fix hour regressed on causal SPY. beta -0.3 bp at t -0.01,
         ranked 24th of 24 hours - while 16 of the 24 hours carry |t| > 2. The
         SPY-GBPUSD relationship is strong across the day and absent at
         precisely the hour the hypothesis named.

    C28  Tokyo 09:55 JST fix, daily, USDJPY. Mean -0.350 bp at t -1.74 against
         a 0.99 bp toll; best-side net -0.642 bp; rank 6 of 24 by |mean|.

    C30  day-of-week at the London fix hour. Best is Wednesday at +0.879 bp,
         net -0.052 bp. Nothing clears.

THE TERMINAL FINDING

    candidate                     gross   detect   toll   need   ratio
    month-end WMR GBPUSD           3.24     3.12   0.93   4.05   0.80x
    triple-swap Thu rollover       0.96     0.44   1.15   1.59   0.60x
    post-fix reversion USDCHF      0.82     0.32   1.29   1.61   0.51x
    day-of-week Wed GBPUSD         0.88     0.96   0.93   1.89   0.47x
    post-fix reversion EURUSD      0.45     0.29   0.85   1.14   0.39x
    Tokyo fix daily USDJPY         0.35     0.22   0.99   1.21   0.29x
    post-fix reversion AUDUSD      0.46     0.36   1.40   1.76   0.26x
    post-fix reversion GBPUSD      0.18     0.32   0.93   1.25   0.14x

    mean 0.43x    best 0.80x    none reaches 1.00x

Every effect measured in this programme lands between 14% and 80% of what it
needed. The structure is a scissors: mechanisms frequent enough to detect
produce moves smaller than the spread, and mechanisms producing moves larger
than the spread occur too rarely to detect within sixteen years. In this
dataset the two constraints close on each other and leave no gap.

That is not a statement about these particular ideas. It is a statement about
retail FX H1 data, where the toll is 0.6 to 1.9 bp and hourly sigma is 8 to 24
bp. Any effect worth trading there has to be about 1 to 2 bp - roughly a tenth
of an hourly standard deviation - and effects that size need thousands of
observations to see. The events that plausibly generate them happen twelve
times a year.

WHAT WOULD CHANGE IT
Not more candidates on this data. Either a lower toll (institutional
execution), a different asset class where the friction-to-signal ratio is
better, or data types this programme never had - options chains, futures term
structure, or a point-in-time equity panel.
"""
