"""The check walk: the steps that test a theory of change against the evidence (task 054).

One module per chain step, with its prompt beside it as ``*_prompt.py``:
``selecting`` (``toc_select`` and ``toc_search_new``), ``discover``, ``merge``,
``judge``, ``figures``, ``choose`` and ``summarise``. ``shared`` holds the reads
every step uses; ``grade`` holds the evidence verdict rule (simplified BEAM).

Each step has the scoping steps' shape, ``(conn, *, task_id, run_id, context,
backend)``, and writes through :mod:`~policy_atlas.theory_of_change.store`.
"""
