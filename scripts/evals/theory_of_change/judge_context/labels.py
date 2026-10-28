# Lead labels: acceptable stances per question. S supports, C challenges, N not_about.
S, C, N = "supports", "challenges", "not_about"
ANY = {S, C, N}
LABELS = {
 "2018a1e8-af22-4dc5-8056-6d73a01d6f62": {  # lower excess energy -> lower obesity
  "10.1136/bmj.38077.458438.ee": ({S}, {S}),        # James 2004, England trial
  "10.1542/peds.2005-0983": ({S, C}, ANY),          # Ebbeling 2006 pilot
  "10.1136/bmj.39342.571806.55": ({C, N}, {C, N}),  # James 2007: intake at 3 years not reported
  "10.1111/j.1467-789x.2007.00310.x": ({N}, {N}),   # commentary, full text
  "10.1111/j.1467-789x.2004.00133.x": ({N}, {N}),   # policy commentary, full text
  "10.1056/nejmoa1203034": ({S}, {S, N}),           # de Ruyter, NL
  "10.1056/nejmoa1203388": ({S, C}, ANY),           # Ebbeling 2012
  "10.1016/s2213-8587(13)70051-2": ({S}, {S, N}),   # Hall model
  "10.1371/journal.pmed.1003212": ({S, N}, {S, N}), # Mytton model
  "10.1136/bmj.e7492": ({S}, {S, N}),               # Te Morenga SR
  "10.1017/s1368980008002644": ({S}, {S, N}),       # Sichieri, Brazil
  "10.1136/bmj.320.7244.1240": ({N}, {N}),          # Cole definition
  "10.1371/journal.pmed.1003915": ({N}, {N}),       # TfL purchases
  "10.1371/journal.pone.0031578": ({N}, {N}),       # Adams exposure
 },
 "b2eff091-ee50-47dc-a0d7-ad5e02e72d62": {  # fewer ads seen -> eat fewer snacks
  "10.1111/obr.12812": ({S}, {S, N}),
  "10.1017/s1368980007001231": ({S}, {S}),          # Halford, UK
  "10.1542/peds.2018-2554": ({S}, {S}),             # Coates, UK RCT
  "10.1001/jamapediatrics.2022.1037": ({S}, {S, N}),
  "10.1111/ijpo.12735": ({C, N}, {C, N}),           # Jensen, not mediated by ads
  "10.1371/journal.pone.0031578": ({N}, {N}),       # exposure: step before
  "10.1017/s1368980019003355": ({N}, {N}),          # exposure: step before
  "10.1371/journal.pmed.1003915": ({S, N}, {S, N}),
  "10.1371/journal.pmed.1003212": ({S, N}, {S, N}),
  "10.1136/bmj.38077.458438.ee": ({N}, {N}),
 },
 "5635a336-7f75-405d-b888-2200c0f82e4b": {  # restricted ads absent -> children see fewer
  "10.1371/journal.pone.0031578": ({C}, {C}),       # Adams, UK: no change
  "10.1017/s1368980019003355": ({S}, {N}),          # Chile: place-dependent
  "10.1111/obr.13447": ({S}, {N}),
  "10.1186/s13690-025-01774-2": ({C}, {C, N}),      # Portugal
  "10.1016/j.tjnut.2022.09.002": ({C, N}, {N}),     # Quebec
  "10.1371/journal.pmed.1003212": ({N, S}, {S, N}),
  "10.1017/s1368980007001231": ({N}, {N}),          # intake: step after
  "10.1111/obr.12812": ({N}, {N}),                  # intake: step after
  "10.1371/journal.pmed.1003915": ({N}, {N}),
  "10.1111/ijpo.12735": ({S}, {N}),                 # exposure fell in Chile
 },
}
