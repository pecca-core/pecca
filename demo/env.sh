# Sourced (hidden) by demo/quickstart.tape. Run `vhs demo/quickstart.tape` from the repo root.
# Real commands are recorded; only the `pip install` line and the final echo are simulated.
source .venv/bin/activate
export COLUMNS=100 MLFLOW_DISABLE_AGENT_HINT=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
WARM=${PECCA_DEMO_WARM:-/tmp/pecca-demo-warm}
if [ ! -d "$WARM/.pecca/cache" ]; then   # warm the e5 embedding cache once (not recorded)
  mkdir -p "$WARM" && (cd "$WARM" && PECCA_HOME="$WARM/.pecca" pecca datasets demo >/dev/null \
    && PECCA_HOME="$WARM/.pecca" pecca init --profile none >/dev/null \
    && PECCA_HOME="$WARM/.pecca" pecca train default/default/route_rfi --candidates tfidf_linear,e5_logreg >/dev/null 2>&1)
fi
DEMO=$(mktemp -d /tmp/pecca-gif.XXXX) && mkdir -p "$DEMO/.pecca" && cp -R "$WARM/.pecca/cache" "$DEMO/.pecca/cache"
cd "$DEMO"
export PS1='$ '
pip() { echo "Successfully installed pecca-0.1.0"; }
clear
