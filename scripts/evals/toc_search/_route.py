"""Pin the harness's model route before any ``policy_atlas`` module loads.

Several repo modules read the model route once, when they are first imported (for
example the screen and rerank model names), so this runs first. ``backend/.env`` may
select the Bedrock route; this evaluation runs on OpenAI directly (task 054 brief):

- default (``--models 56``): the product's ``openai-direct`` route (gpt-5.6 Luna/Terra);
- ``--models 6x``: the harness-only route in ``model_route_6x.toml`` (screen on
  gpt-6-luna; classify, rerank, judge, planner and web search on gpt-6.1-terra), loaded
  through the route file's overlay variable. The product route file is not touched.
"""

import os
import sys
from pathlib import Path


def _models(argv: list[str]) -> str:
    for i, arg in enumerate(argv):
        if arg.startswith("--models="):
            return arg.split("=", 1)[1]
        if arg == "--models" and i + 1 < len(argv):
            return argv[i + 1]
    return "56"


MODELS = _models(sys.argv)
if MODELS == "6x":
    os.environ["POLICY_ATLAS_MODEL_ROUTE"] = "eval-6x"
    os.environ["POLICY_ATLAS_MODEL_ROUTE_FILE"] = str(
        Path(__file__).with_name("model_route_6x.toml")
    )
else:
    os.environ["POLICY_ATLAS_MODEL_ROUTE"] = "openai-direct"
    os.environ.pop("POLICY_ATLAS_MODEL_ROUTE_FILE", None)
