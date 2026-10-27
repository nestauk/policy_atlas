"""Pin the harness to the OpenAI model route before any ``policy_atlas`` module loads.

Several repo modules read the model route once, when they are first imported (for
example the screen and rerank model names). ``backend/.env`` may select the Bedrock
route; this evaluation runs on the OpenAI route (task 054 brief), so the harness
imports this module first.
"""

import os

os.environ["POLICY_ATLAS_MODEL_ROUTE"] = "openai-direct"
